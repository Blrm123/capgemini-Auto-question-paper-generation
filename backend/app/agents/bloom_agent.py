"""
agents/bloom_agent.py

Bloom Taxonomy Agent for the Agentic Question Paper Generator.

Responsibilities:
  - Read generated_questions from AgentState
  - Call Groq LLM via LLMService to classify each question by Bloom's Taxonomy level
  - Validate every returned BloomItem for required fields and valid level values
  - Ensure every input question has a corresponding output BloomItem
  - Write List[BloomItem] to AgentState.bloom_analysis
  - Handle errors gracefully by appending to AgentState.errors
"""

from typing import Any

from app.models.state import AgentState, BloomItem
from app.prompts.bloom_prompt import (
    BLOOM_SYSTEM_PROMPT,
    build_bloom_user_prompt,
)
from app.services.llm_service import LLMService
from app.services.logger import log_execution_time, setup_logger

logger = setup_logger(__name__)

AGENT_NAME = "BloomAgent"

# Valid Bloom levels exactly as defined in state.py and the prompt
_VALID_BLOOM_LEVELS = {
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
}

# Title-case normalization map — handles LLM capitalisation variants
_BLOOM_NORMALISE: dict[str, str] = {
    level.lower(): level for level in _VALID_BLOOM_LEVELS
}


class BloomAgent:
    """
    Classifies generated exam questions into Bloom's Taxonomy levels.

    LangGraph node function: bloom_agent_node()
    """

    def __init__(self) -> None:
        self.llm = LLMService()
        logger.info(f"{AGENT_NAME} initialized.")

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Reads:  state["generated_questions"]
        Writes: state["bloom_analysis"], state["current_agent"],
                state["status"], state["errors"]

        Args:
            state: The shared AgentState dict.

        Returns:
            Partial state update dict for LangGraph to merge.
        """
        with log_execution_time(logger, AGENT_NAME):
            return self._run(state)

    def _run(self, state: AgentState) -> dict[str, Any]:
        """Core logic separated from the context manager for clarity."""

        errors: list[str] = list(state.get("errors", []))

        # ------------------------------------------------------------------
        # 1. Guard: propagate failed state without executing
        # ------------------------------------------------------------------
        if state.get("status") == "failed":
            logger.warning(
                f"{AGENT_NAME}: Skipping because workflow status is 'failed'."
            )
            return {
                "bloom_analysis": [],
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        # ------------------------------------------------------------------
        # 2. Guard: generated_questions must be non-empty
        # ------------------------------------------------------------------
        generated_questions: list = state.get("generated_questions", [])
        if not generated_questions:
            error_msg = (
                f"{AGENT_NAME}: generated_questions is empty. "
                "Cannot classify questions without generated content."
            )
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "bloom_analysis": [],
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        logger.info(
            f"{AGENT_NAME}: Classifying {len(generated_questions)} question(s) "
            "by Bloom's Taxonomy level."
        )
        # ------------------------------------------------------------------
        # 3. Call LLM to classify questions in batches of ≤8
        #    (prevents hitting Groq 4096 output token limit on large papers)
        # ------------------------------------------------------------------
        BATCH_SIZE = 8
        raw_data: list = []
        batches = [
            generated_questions[i:i + BATCH_SIZE]
            for i in range(0, len(generated_questions), BATCH_SIZE)
        ]
        logger.info(f"{AGENT_NAME}: Processing {len(generated_questions)} question(s) in {len(batches)} batch(es).")

        for batch_idx, batch in enumerate(batches):
            try:
                user_prompt = build_bloom_user_prompt(batch)
                batch_result = self.llm.call_llm_for_json(
                    system_prompt=BLOOM_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    agent_name=AGENT_NAME,
                    max_tokens=2048,
                )
                if isinstance(batch_result, list):
                    raw_data.extend(batch_result)
                    logger.info(f"{AGENT_NAME}: Batch {batch_idx + 1}/{len(batches)} returned {len(batch_result)} item(s).")
                else:
                    logger.warning(f"{AGENT_NAME}: Batch {batch_idx + 1} returned non-list — applying heuristic fallback for batch.")
                    raw_data.extend([])
            except Exception as exc:
                logger.warning(
                    f"{AGENT_NAME}: Batch {batch_idx + 1} LLM call failed ({exc}). Heuristic fallback will apply for these questions."
                )
                # Don't append anything — heuristic fallback below will cover missing IDs

        if not isinstance(raw_data, list):
            raw_data = []

        # ------------------------------------------------------------------
        # 5. Build a lookup of input questions by id for cross-reference
        # ------------------------------------------------------------------
        input_by_id: dict[str, dict] = {
            q["id"]: q for q in generated_questions if "id" in q
        }

        # ------------------------------------------------------------------
        # 6. Validate and coerce each item into BloomItem structure
        # ------------------------------------------------------------------
        bloom_analysis: list[BloomItem] = []
        item_warnings: list[str] = []
        seen_ids: set[str] = set()

        for idx, item in enumerate(raw_data):
            if not isinstance(item, dict):
                continue

            q_id = item.get("id")
            question = item.get("question")
            marks = item.get("marks")
            difficulty = item.get("difficulty")
            bloom_level = item.get("bloom_level")
            bloom_justification = item.get("bloom_justification")

            if not q_id or not isinstance(q_id, str):
                continue

            q_id = q_id.strip()
            if q_id in seen_ids:
                continue
            seen_ids.add(q_id)

            # --- question text: fall back to input question ---
            if not question or not isinstance(question, str):
                if q_id in input_by_id:
                    question = input_by_id[q_id]["question"]
                else:
                    continue

            # --- marks: coerce to int, fall back to input ---
            try:
                marks = int(marks)
            except (ValueError, TypeError):
                if q_id in input_by_id:
                    marks = input_by_id[q_id]["marks"]
                else:
                    continue

            # --- difficulty: fallback to input ---
            if not difficulty or not isinstance(difficulty, str):
                if q_id in input_by_id:
                    difficulty = input_by_id[q_id]["difficulty"]
                else:
                    continue
            difficulty = difficulty.strip().lower()

            # --- bloom_level: normalise capitalisation, validate ---
            normalised_level = _BLOOM_NORMALISE.get(str(bloom_level).strip().lower()) if bloom_level else None
            if not normalised_level:
                # Heuristic fallback if LLM gave an invalid level
                normalised_level, fallback_just = self._heuristic_classify(question)
                bloom_justification = bloom_justification or fallback_just

            if not bloom_justification or not isinstance(bloom_justification, str):
                bloom_justification = (
                    f"Classified as {normalised_level} based on the cognitive demand of the question."
                )

            image_path = None
            if q_id in input_by_id:
                image_path = input_by_id[q_id].get("image_path")
                
            options = item.get("options")
            if not options and q_id in input_by_id:
                options = input_by_id[q_id].get("options")
                
            correct_answer = item.get("correct_answer")
            if not correct_answer and q_id in input_by_id:
                correct_answer = input_by_id[q_id].get("correct_answer")

            bloom_analysis.append(
                BloomItem(
                    id=q_id,
                    question=question.strip(),
                    marks=marks,
                    difficulty=difficulty,
                    bloom_level=normalised_level,
                    bloom_justification=bloom_justification.strip(),
                    image_path=image_path,
                    options=options if isinstance(options, list) and len(options) == 4 else None,
                    correct_answer=str(correct_answer).strip() if correct_answer else None,
                )
            )

        # ------------------------------------------------------------------
        # 7. Fallback for any input questions omitted by the LLM
        # ------------------------------------------------------------------
        for q in generated_questions:
            q_id = q.get("id")
            if q_id and q_id not in seen_ids:
                h_level, h_just = self._heuristic_classify(q.get("question", ""))
                bloom_analysis.append(
                    BloomItem(
                        id=q_id,
                        question=q.get("question", "").strip(),
                        marks=int(q.get("marks", 5)),
                        difficulty=str(q.get("difficulty", "medium")).lower(),
                        bloom_level=h_level,
                        bloom_justification=h_just,
                        image_path=q.get("image_path"),
                        options=q.get("options"),
                        correct_answer=q.get("correct_answer"),
                    )
                )
                seen_ids.add(q_id)

        logger.info(
            f"{AGENT_NAME}: Successfully classified {len(bloom_analysis)} question(s). "
            f"Levels used: {sorted({item['bloom_level'] for item in bloom_analysis})}"
        )

        return {
            "bloom_analysis": bloom_analysis,
            "current_agent": AGENT_NAME,
            "status": "running",
            "errors": errors,
        }

    def _heuristic_classify(self, question_text: str) -> tuple[str, str]:
        """Heuristic classification based on question verbs if LLM output is missing."""
        text = question_text.lower()
        if any(k in text for k in ["case study", "design", "construct", "prove"]):
            level = "Create" if "design" in text or "case study" in text else "Apply"
        elif any(k in text for k in ["calculate", "compute", "solve", "find", "determine", "multiply"]):
            level = "Apply"
        elif any(k in text for k in ["compare", "contrast", "differentiate", "analyze"]):
            level = "Analyze"
        elif any(k in text for k in ["evaluate", "justify", "verify", "critique"]):
            level = "Evaluate"
        elif any(k in text for k in ["explain", "describe", "discuss", "summarize"]):
            level = "Understand"
        else:
            level = "Remember"
        return level, f"Classified as {level} based on cognitive demand and action verbs."


# ---------------------------------------------------------------------------
# LangGraph Node Function
# ---------------------------------------------------------------------------
_bloom_agent = BloomAgent()


def bloom_agent_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible node function for the Bloom Taxonomy Agent.

    This is the function registered with StateGraph.add_node().

    Args:
        state: The shared AgentState dict passed by LangGraph.

    Returns:
        Partial state update dict.
    """
    return _bloom_agent(state)
