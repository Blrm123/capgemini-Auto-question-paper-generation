"""
agents/image_descriptor_agent.py

Image Descriptor Agent for the Agentic Question Paper Generator.

Responsibilities:
  - Run Stage 1: Cheap relevance ranking using CLIP (sentence-transformers).
    Compare all extracted images against syllabus topics to identify top 1-3 candidates.
  - Run Stage 2: Deep understanding/annotation using Groq Vision (describe_image)
    ONLY on the selected top candidate images.
  - Update AgentState's content_context and rag_chunks with the detailed descriptions.
"""

import os
import re
from typing import Any, Dict, List, Tuple
from PIL import Image

from app.config import settings
from app.models.state import AgentState, SyllabusTopic, RagChunk
from app.services.llm_service import LLMService
from app.services.logger import log_execution_time, setup_logger

logger = setup_logger(__name__)

AGENT_NAME = "ImageDescriptorAgent"


class ImageDescriptorAgent:
    """
    Ranks images using CLIP and generates detailed descriptions only for top-scoring candidates.

    LangGraph node function: image_descriptor_agent_node()
    """

    def __init__(self) -> None:
        self.llm = LLMService()
        logger.info(f"{AGENT_NAME} initialized.")

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Reads: state["rag_chunks"], state["syllabus_topics"], state["content_context"]
        Writes: state["rag_chunks"], state["content_context"], state["current_agent"], state["status"], state["errors"]
        """
        with log_execution_time(logger, AGENT_NAME):
            return self._run(state)

    def _run(self, state: AgentState) -> dict[str, Any]:
        errors: list[str] = list(state.get("errors", []))

        # 1. Guard: workflow must not already be in failed state
        if state.get("status") == "failed":
            logger.warning(f"{AGENT_NAME}: Skipping because workflow status is 'failed'.")
            return {
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        # 2. Extract all unique image paths and placeholder info from chunks
        unique_images: Dict[str, Dict[str, Any]] = {}
        for chunk in state.get("rag_chunks", []):
            img_path = chunk.get("image_path")
            img_id = chunk.get("image_id")
            img_expl = chunk.get("image_explanation")
            if img_path and img_id:
                unique_images[img_path] = {
                    "image_id": img_id,
                    "image_explanation": img_expl or ""
                }

        # Load image registry to filter only academic images
        try:
            import sys
            import importlib
            # Ensure rag/ is on sys.path (same base as rag_service.py)
            rag_base = str(settings.paths.BASE_DIR / "rag")
            if rag_base not in sys.path:
                sys.path.insert(0, rag_base)
            # Use importlib to avoid IDE false-positive 'unresolved import' warnings
            _mod = importlib.import_module("src.ingestion.image_registry")
            ImageRegistry = _mod.ImageRegistry
            registry = ImageRegistry(settings.paths.BASE_DIR)
            registry.load()
            
            academic_paths = {rec.relative_path for rec in registry.get_academic_records()}
            if academic_paths:
                filtered_images = {path: info for path, info in unique_images.items() if path in academic_paths}
                if filtered_images:
                    unique_images = filtered_images
                    logger.info(f"{AGENT_NAME}: Filtered down to {len(unique_images)} academic image(s) via registry.")
                else:
                    logger.info(f"{AGENT_NAME}: No image paths matched academic registry records.")
        except Exception as reg_err:
            logger.warning(f"{AGENT_NAME}: Could not load image registry ({reg_err}). Using all chunk images.")

        if not unique_images:
            logger.info(f"{AGENT_NAME}: No academic images found in document chunks. Skipping ranking.")
            return {
                "current_agent": AGENT_NAME,
                "status": "running",
                "errors": errors,
            }

        logger.info(f"{AGENT_NAME}: Found {len(unique_images)} unique images to rank.")

        # 3. Extract syllabus topic strings to use as queries
        topics: List[str] = []
        for unit in state.get("syllabus_topics", []):
            unit_name = unit.get("unit_name", "")
            if unit_name:
                topics.append(unit_name)
            topics.extend(unit.get("topics", []))

        if not topics:
            logger.warning(f"{AGENT_NAME}: No structured syllabus topics found. Falling back to syllabus_context.")
            syllabus_context = state.get("syllabus_context") or ""
            # Truncate fallback query to avoid huge input text embedding
            topics = [syllabus_context[:1000]] if syllabus_context else ["syllabus diagram flow chart structure outline"]

        # 4. Load CLIP and perform similarity scoring (Stage 1)
        selected_images: List[Tuple[str, float]] = []
        try:
            from sentence_transformers import SentenceTransformer, util
            import torch

            # Load model on CPU
            logger.info(f"{AGENT_NAME}: Loading clip-ViT-B-32 for relevance ranking...")
            model = SentenceTransformer('clip-ViT-B-32', device='cpu')

            # Load images
            pil_images = []
            image_paths = []
            for img_path in unique_images.keys():
                abs_path = settings.paths.BASE_DIR / img_path
                if abs_path.is_file():
                    try:
                        pil_images.append(Image.open(abs_path))
                        image_paths.append(img_path)
                    except Exception as img_err:
                        logger.error(f"{AGENT_NAME}: Failed to load image {abs_path}: {img_err}")
                else:
                    logger.warning(f"{AGENT_NAME}: Image path not found: {abs_path}")

            if pil_images:
                logger.info(f"{AGENT_NAME}: Embedding {len(pil_images)} images and {len(topics)} topics...")
                image_embeddings = model.encode(pil_images, batch_size=len(pil_images), convert_to_tensor=True)
                text_embeddings = model.encode(topics, convert_to_tensor=True)

                # Compute cosine similarity matrix
                similarity = util.cos_sim(text_embeddings, image_embeddings)

                # Find maximum similarity score for each image across all topics
                max_scores = torch.max(similarity, dim=0).values.tolist()

                # Rank images
                ranked = sorted(zip(image_paths, max_scores), key=lambda x: x[1], reverse=True)
                
                # Select top 3 images
                top_k = min(3, len(ranked))
                selected_images = ranked[:top_k]
                logger.info(f"{AGENT_NAME}: Top {top_k} ranked images: {selected_images}")
            else:
                logger.warning(f"{AGENT_NAME}: No valid images could be loaded for ranking.")

        except Exception as clip_err:
            logger.warning(f"{AGENT_NAME}: CLIP ranking failed: {clip_err}. Falling back to default top-3 images.")
            # Fallback: pick the first 3 image paths
            selected_images = [(img_path, 1.0) for img_path in list(unique_images.keys())[:3]]

        # 5. Run expensive vision model only on selected images (Stage 2)
        detailed_descriptions: Dict[str, str] = {}
        for img_path, score in selected_images:
            abs_path = settings.paths.BASE_DIR / img_path
            logger.info(f"{AGENT_NAME}: Generating detailed description for {img_path} (score: {score:.4f})...")
            try:
                description = self.llm.describe_image(str(abs_path))
                detailed_descriptions[img_path] = description
            except Exception as vision_err:
                error_msg = f"{AGENT_NAME}: Vision description failed for {img_path}: {vision_err}"
                logger.warning(error_msg)
                errors.append(error_msg)

        # 6. Update State: rag chunks and both contexts.  The syllabus agent
        # runs after this node so diagram descriptions can supply meaningful
        # source content for image-only or diagram-heavy PDFs.
        updated_chunks: List[RagChunk] = []
        for chunk in state.get("rag_chunks", []):
            img_path = chunk.get("image_path")
            new_chunk = dict(chunk)
            if img_path in detailed_descriptions:
                desc = detailed_descriptions[img_path]
                new_chunk["image_explanation"] = desc
                # Update chunk content replacing placeholder
                if new_chunk.get("content"):
                    new_chunk["content"] = re.sub(
                        r"\[Image Description:.*?\]",
                        lambda m, d=desc: f"[Image Description: {d}]",
                        new_chunk["content"]
                    )
            updated_chunks.append(new_chunk)  # type: ignore

        content_context = state.get("content_context") or ""
        syllabus_context = state.get("syllabus_context") or ""
        for img_path, desc in detailed_descriptions.items():
            # Find the original placeholder explanation from rag_chunks
            placeholder = unique_images.get(img_path, {}).get("image_explanation")
            if placeholder:
                old_placeholder_pattern = f"[Image Description: {placeholder}]"
                new_desc_pattern = f"[Image Description: {desc}]"
                content_context = content_context.replace(old_placeholder_pattern, new_desc_pattern)
                syllabus_context = syllabus_context.replace(old_placeholder_pattern, new_desc_pattern)

        logger.info(f"{AGENT_NAME}: State updated with {len(detailed_descriptions)} detailed description(s).")

        return {
            "rag_chunks": updated_chunks,
            "content_context": content_context,
            "syllabus_context": syllabus_context,
            "current_agent": AGENT_NAME,
            "status": "running",
            "errors": errors,
        }


# LangGraph Node Function
_image_descriptor_agent = ImageDescriptorAgent()


def image_descriptor_agent_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible node function for the Image Descriptor Agent.
    """
    return _image_descriptor_agent(state)
