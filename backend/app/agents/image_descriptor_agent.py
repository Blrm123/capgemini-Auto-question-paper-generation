"""
agents/image_descriptor_agent.py

Image Descriptor Agent — Gemini-powered multimodal academic image analysis.

This agent runs AFTER SyllabusAgent so it has access to real topic names.

Responsibilities:
  1. Load the ImageRegistry to get all academic images from the uploaded PDF.
  2. Select the top-N images by quality_score (default: top 10).
  3. Send each image to Gemini Flash (native multimodal) with a structured prompt
     that asks for: concept, unit_hint, components, learning_objective, exam hints.
  4. Store the structured results in state["image_topic_map"]:
         { image_id: { concept, unit_hint, components, learning_objective,
                       exam_q1, exam_q2, description, image_path } }
  5. Update chunk image_explanation fields with the rich descriptions.
  6. Update content_context with the enriched descriptions.

No CLIP required. No sentence-transformers. Gemini handles image+text understanding
natively in a single call — far more accurate than CLIP cosine similarity.
"""

import importlib
import os
import re
import sys
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.state import AgentState, RagChunk
from app.services.llm_service import LLMService
from app.services.logger import log_execution_time, setup_logger

logger = setup_logger(__name__)

AGENT_NAME = "ImageDescriptorAgent"

# Maximum number of images to describe (ordered by quality_score desc).
# Top-10 gives excellent coverage while keeping API cost reasonable.
MAX_IMAGES_TO_DESCRIBE = int(__import__("os").getenv("MAX_IMAGES_TO_DESCRIBE", "10"))


def _parse_structured_description(raw: str) -> dict[str, str]:
    """
    Parse the structured Gemini response into a dict.

    Expected format from LLMService.describe_image():
        CONCEPT: ...
        UNIT_HINT: ...
        COMPONENTS: ...
        LEARNING_OBJECTIVE: ...
        EXAM_Q1: ...
        EXAM_Q2: ...
    """
    fields = {
        "concept": "",
        "unit_hint": "",
        "components": "",
        "learning_objective": "",
        "exam_q1": "",
        "exam_q2": "",
    }
    patterns = {
        "concept":            r"CONCEPT:\s*(.*?)(?=\n[A-Z_]+:|$)",
        "unit_hint":          r"UNIT_HINT:\s*(.*?)(?=\n[A-Z_]+:|$)",
        "components":         r"COMPONENTS:\s*(.*?)(?=\n[A-Z_]+:|$)",
        "learning_objective": r"LEARNING_OBJECTIVE:\s*(.*?)(?=\n[A-Z_]+:|$)",
        "exam_q1":            r"EXAM_Q1:\s*(.*?)(?=\n[A-Z_]+:|$)",
        "exam_q2":            r"EXAM_Q2:\s*(.*?)(?=\n[A-Z_]+:|$)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        if m:
            fields[key] = m.group(1).strip()

    # Fallback if raw text was plain prose without CONCEPT: header
    if not fields["concept"] and raw.strip():
        fields["concept"] = raw.strip()

    return fields


def _format_rich_desc(entry: dict) -> str:
    """Format a clean description string from an image_topic_map entry."""
    concept = entry.get("concept", "").strip()
    components = entry.get("components", "").strip()
    objective = entry.get("learning_objective", "").strip()

    if not components and not objective:
        return concept

    parts = []
    if concept:
        parts.append(f"Concept: {concept}")
    if components:
        parts.append(f"Components: {components}")
    if objective:
        parts.append(f"Learning objective: {objective}")

    return ". ".join(parts) if parts else concept


class ImageDescriptorAgent:
    """
    Describes academic images using Gemini's native multimodal vision.

    Runs AFTER SyllabusAgent so it can use real topic names in the vision prompt.
    """

    def __init__(self) -> None:
        self.llm = LLMService()
        logger.info(f"{AGENT_NAME} initialized.")

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node entry point."""
        with log_execution_time(logger, AGENT_NAME):
            return self._run(state)

    def _run(self, state: AgentState) -> dict[str, Any]:
        errors: list[str] = list(state.get("errors", []))

        # Guard: skip if workflow already failed
        if state.get("status") == "failed":
            logger.warning(f"{AGENT_NAME}: Skipping because workflow status is 'failed'.")
            return {
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
                "image_topic_map": {},
            }

        # ----------------------------------------------------------------
        # 1. Load ImageRegistry to get academic images
        # ----------------------------------------------------------------
        academic_records: List[Any] = []
        try:
            rag_base = str(settings.paths.BASE_DIR / "rag")
            if rag_base not in sys.path:
                sys.path.insert(0, rag_base)
            _mod = importlib.import_module("src.ingestion.image_registry")
            ImageRegistry = _mod.ImageRegistry
            registry = ImageRegistry(settings.paths.BASE_DIR)
            registry.load()
            academic_records = registry.get_academic_records()
        except Exception as reg_err:
            logger.warning(
                f"{AGENT_NAME}: Could not load image registry ({reg_err}). "
                "Skipping image description."
            )

        if not academic_records:
            logger.info(f"{AGENT_NAME}: No academic images in registry. Skipping.")
            return {
                "current_agent": AGENT_NAME,
                "status": "running",
                "errors": errors,
                "image_topic_map": {},
            }

        logger.info(
            f"{AGENT_NAME}: Found {len(academic_records)} academic image(s) in registry."
        )

        # ----------------------------------------------------------------
        # 2. Sort by quality_score descending, take top-N
        # ----------------------------------------------------------------
        sorted_records = sorted(
            academic_records,
            key=lambda r: getattr(r, "quality_score", 0.0),
            reverse=True,
        )
        selected_records = sorted_records[:MAX_IMAGES_TO_DESCRIBE]
        logger.info(
            f"{AGENT_NAME}: Selected top-{len(selected_records)} images "
            f"(by quality_score) for Gemini vision analysis."
        )

        # ----------------------------------------------------------------
        # 3. Build syllabus context hint
        # ----------------------------------------------------------------
        syllabus_topics = state.get("syllabus_topics", [])
        topic_names: List[str] = []
        for unit in syllabus_topics:
            if isinstance(unit, dict):
                unit_name = unit.get("unit_name", "")
                if unit_name:
                    topic_names.append(unit_name)
                topic_names.extend(str(t) for t in unit.get("topics", []))
        syllabus_hint = ", ".join(topic_names[:20]) if topic_names else ""

        # ----------------------------------------------------------------
        # 4. Describe each selected image with Gemini vision (CONCURRENT)
        # ----------------------------------------------------------------
        image_topic_map: Dict[str, Any] = {}
        import concurrent.futures

        def _process_image(rec):
            img_path_abs = str(settings.paths.BASE_DIR / rec.relative_path)
            img_id = rec.image_id

            # Verify image file exists
            if not os.path.isfile(img_path_abs):
                logger.warning(f"{AGENT_NAME}: Image file not found: {img_path_abs}. Skipping.")
                return img_id, None, None

            logger.info(
                f"{AGENT_NAME}: Describing image {img_id} "
                f"(quality={getattr(rec, 'quality_score', 0.0):.2f}) ..."
            )

            try:
                raw_description = self.llm.describe_image(
                    image_path=img_path_abs,
                    syllabus_context=syllabus_hint,
                )
                parsed = _parse_structured_description(raw_description)
                parsed["description"] = raw_description
                parsed["image_path"] = rec.relative_path
                
                logger.info(
                    f"{AGENT_NAME}: {img_id} -> concept='{parsed.get('concept', '')[:60]}'"
                )
                return img_id, parsed, None
            except Exception as vision_err:
                error_msg = f"{AGENT_NAME}: Vision description failed for {img_id}: {vision_err}"
                logger.warning(error_msg)
                fallback = {
                    "concept": getattr(rec, "caption", ""),
                    "unit_hint": "",
                    "components": "",
                    "learning_objective": "",
                    "exam_q1": "",
                    "exam_q2": "",
                    "description": getattr(rec, "caption", ""),
                    "image_path": rec.relative_path,
                }
                return img_id, fallback, error_msg

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_IMAGES_TO_DESCRIBE) as executor:
            futures = [executor.submit(_process_image, rec) for rec in selected_records]
            for future in concurrent.futures.as_completed(futures):
                img_id, parsed, error_msg = future.result()
                if parsed is not None:
                    image_topic_map[img_id] = parsed
                if error_msg:
                    errors.append(error_msg)

        # ----------------------------------------------------------------
        # 5. Update rag_chunks with enriched image_explanation
        # ----------------------------------------------------------------
        updated_chunks: List[RagChunk] = []
        for chunk in state.get("rag_chunks", []):
            img_id = chunk.get("image_id")
            new_chunk = dict(chunk)
            if img_id and img_id in image_topic_map:
                entry = image_topic_map[img_id]
                rich_desc = _format_rich_desc(entry)
                new_chunk["image_explanation"] = rich_desc
                if new_chunk.get("content"):
                    new_chunk["content"] = re.sub(
                        r"\[Image Description:.*?\]",
                        lambda m, d=rich_desc: f"[Image Description: {d}]",
                        new_chunk["content"],
                    )
            updated_chunks.append(new_chunk)  # type: ignore

        # ----------------------------------------------------------------
        # 6. Update content_context string with enriched descriptions
        # ----------------------------------------------------------------
        content_context = state.get("content_context") or ""
        syllabus_context = state.get("syllabus_context") or ""

        for img_id, entry in image_topic_map.items():
            rich_desc = _format_rich_desc(entry)
            content_context = re.sub(
                r"\[Image Description:.*?\]",
                lambda m, d=rich_desc: f"[Image Description: {d}]",
                content_context,
            )

        logger.info(
            f"{AGENT_NAME}: Completed. Described {len(image_topic_map)} image(s). "
            f"image_topic_map keys: {list(image_topic_map.keys())}"
        )

        return {
            "rag_chunks": updated_chunks,
            "content_context": content_context,
            "syllabus_context": syllabus_context,
            "image_topic_map": image_topic_map,
            "current_agent": AGENT_NAME,
            "status": "running",
            "errors": errors,
        }


# LangGraph Node Function
_image_descriptor_agent = ImageDescriptorAgent()


def image_descriptor_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph-compatible node function for the Image Descriptor Agent."""
    return _image_descriptor_agent(state)
