"""
agents/syllabus_agent.py

Syllabus Agent for the Agentic Question Paper Generator.

Responsibilities:
  - Read RAG-retrieved syllabus context from AgentState.syllabus_context
  - Call Groq LLM via LLMService to extract structured syllabus topics
  - Validate the JSON response structure
  - Write List[SyllabusTopic] to AgentState.syllabus_topics
  - Handle errors gracefully by appending to AgentState.errors
"""

from typing import Any, Optional

from app.models.state import AgentState, SyllabusTopic
from app.prompts.syllabus_prompt import (
    SYLLABUS_SYSTEM_PROMPT,
    build_syllabus_user_prompt,
)
from app.services.llm_service import LLMService
from app.services.logger import log_execution_time, setup_logger

logger = setup_logger(__name__)

AGENT_NAME = "SyllabusAgent"


class SyllabusAgent:
    """
    Extracts structured syllabus topics from RAG-retrieved document chunks.

    LangGraph node function: syllabus_agent_node()
    This class is instantiated once; its __call__ method is the node function.
    """

    def __init__(self) -> None:
        self.llm = LLMService()
        logger.info(f"{AGENT_NAME} initialized.")

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Reads: state["syllabus_context"]
        Writes: state["syllabus_topics"], state["current_agent"],
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
        # 1. Guard: syllabus_context must exist and be non-empty
        # ------------------------------------------------------------------
        syllabus_context: Optional[str] = state.get("syllabus_context")

        if not syllabus_context or not syllabus_context.strip():
            error_msg = (
                f"{AGENT_NAME}: syllabus_context is empty or missing. "
                "Cannot extract syllabus topics from RAG chunks."
            )
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "syllabus_topics": [],
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        # ------------------------------------------------------------------
        # 2. Call LLM to extract syllabus topics
        # ------------------------------------------------------------------
        raw_data = None
        
        try:
            user_prompt = build_syllabus_user_prompt(syllabus_context)
            raw_data = self.llm.call_llm_for_json(
                system_prompt=SYLLABUS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                agent_name=AGENT_NAME,
            )
        except (RuntimeError, ValueError) as exc:
            logger.warning(f"{AGENT_NAME}: LLM call with syllabus_context failed: {exc}. Trying fallback to content_context.")

        # If LLM returned empty list or failed, fall back to content_context
        if not isinstance(raw_data, list) or len(raw_data) == 0:
            logger.warning(
                f"{AGENT_NAME}: LLM returned no syllabus topics for syllabus_context. "
                "Falling back to content_context."
            )
            content_context: Optional[str] = state.get("content_context")
            if content_context and content_context.strip():
                try:
                    # Truncate fallback context to 15000 chars to avoid TPM limit errors
                    truncated_context = content_context[:15000]
                    user_prompt = build_syllabus_user_prompt(truncated_context)
                    raw_data = self.llm.call_llm_for_json(
                        system_prompt=SYLLABUS_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        agent_name=AGENT_NAME,
                    )
                except (RuntimeError, ValueError) as exc:
                    error_msg = f"{AGENT_NAME}: LLM fallback call with content_context failed — {exc}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    return {
                        "syllabus_topics": [],
                        "current_agent": AGENT_NAME,
                        "status": "failed",
                        "errors": errors,
                    }
            else:
                logger.warning(f"{AGENT_NAME}: content_context is empty or missing. Cannot perform fallback.")

        # ------------------------------------------------------------------
        # 3. Validate response is a non-empty list
        # ------------------------------------------------------------------
        # ------------------------------------------------------------------
        # 3. Handle wrapper dicts and nested arrays (e.g. [[{...}]])
        # ------------------------------------------------------------------
        if isinstance(raw_data, dict):
            for key, val in raw_data.items():
                if isinstance(val, list) and len(val) > 0:
                    logger.info(f"{AGENT_NAME}: Unwrapped list from dict key '{key}'.")
                    raw_data = val
                    break

        if isinstance(raw_data, list):
            # Flatten nested lists recursively if LLM returned 2D array [[{...}]]
            flat_items = []
            def _flatten(arr):
                for elem in arr:
                    if isinstance(elem, list):
                        _flatten(elem)
                    elif isinstance(elem, dict):
                        flat_items.append(elem)
                    elif isinstance(elem, str) and elem.strip().startswith("{") and elem.strip().endswith("}"):
                        try:
                            import json
                            flat_items.append(json.loads(elem.strip()))
                        except Exception:
                            pass
            _flatten(raw_data)
            if flat_items:
                raw_data = flat_items

        if not isinstance(raw_data, list) or len(raw_data) == 0:
            result_description = (
                "an empty JSON array"
                if isinstance(raw_data, list)
                else type(raw_data).__name__ if raw_data is not None else "no result"
            )
            error_msg = (
                f"{AGENT_NAME}: LLM could not extract any syllabus units. "
                f"Expected a non-empty JSON array, got {result_description}. "
                "Upload a document containing readable course content or diagrams that can be described."
            )
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "syllabus_topics": [],
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        # ------------------------------------------------------------------
        # 4. Validate and coerce each item into SyllabusTopic structure
        # ------------------------------------------------------------------
        syllabus_topics: list[SyllabusTopic] = []
        validation_errors: list[str] = []

        for idx, item in enumerate(raw_data):
            if not isinstance(item, dict):
                continue

            # Flexible field extraction for key variants (e.g. name, title, subtopics)
            unit_number = (
                item.get("unit_number")
                if item.get("unit_number") is not None
                else item.get("unit")
                if item.get("unit") is not None
                else item.get("unit_no")
                if item.get("unit_no") is not None
                else item.get("number")
                if item.get("number") is not None
                else idx + 1  # Fallback to index + 1 if missing
            )
            unit_name = (
                item.get("unit_name")
                or item.get("name")
                or item.get("title")
                or item.get("unit_title")
                or item.get("module_name")
                or f"Unit {unit_number}"
            )
            raw_topics = (
                item.get("topics")
                or item.get("subtopics")
                or item.get("topic_list")
                or item.get("sub_topics")
                or []
            )

            # Check required fields
            if not unit_name or not isinstance(unit_name, str):
                continue

            # Coerce unit_number to int in case LLM returns it as a string
            try:
                unit_number = int(unit_number)
            except (ValueError, TypeError):
                unit_number = idx + 1

            # Filter out junk topic strings like 'n', '\n', single letters or empty lines
            if isinstance(raw_topics, str):
                raw_topics = [t.strip() for t in raw_topics.split("\n") if t.strip()]

            clean_topics: list[str] = []
            if isinstance(raw_topics, list):
                for t in raw_topics:
                    t_str = str(t).strip()
                    if t_str and t_str.casefold() not in ("n", "\\n", "none", "null") and len(t_str) > 1:
                        clean_topics.append(t_str)

            if not clean_topics:
                validation_errors.append(
                    f"{AGENT_NAME}: Item {idx} ('{unit_name}') has no valid topic strings — skipped."
                )
                continue

            syllabus_topics.append(
                SyllabusTopic(
                    unit_number=unit_number,
                    unit_name=unit_name.strip(),
                    topics=clean_topics,
                )
            )

        # Log any per-item validation warnings (non-fatal)
        for warning in validation_errors:
            logger.warning(warning)

        # ------------------------------------------------------------------
        # 5. Final guard: at least one valid unit must have been extracted
        # ------------------------------------------------------------------
        if not syllabus_topics:
            error_msg = (
                f"{AGENT_NAME}: No valid syllabus units could be extracted "
                "from the LLM response. Check the uploaded document format."
            )
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "syllabus_topics": [],
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        logger.info(
            f"{AGENT_NAME}: Successfully extracted {len(syllabus_topics)} unit(s) "
            f"with {sum(len(u['topics']) for u in syllabus_topics)} total topic(s)."
        )

        # ------------------------------------------------------------------
        # 6. Return partial state update
        # ------------------------------------------------------------------
        return {
            "syllabus_topics": syllabus_topics,
            "current_agent": AGENT_NAME,
            "status": "running",
            "errors": errors,
        }


# ---------------------------------------------------------------------------
# LangGraph Node Function
# ---------------------------------------------------------------------------
# Instantiated once at import time; reused across workflow invocations.
_syllabus_agent = SyllabusAgent()


def syllabus_agent_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph-compatible node function for the Syllabus Agent.

    This is the function registered with StateGraph.add_node().
    It delegates to the SyllabusAgent singleton.

    Args:
        state: The shared AgentState dict passed by LangGraph.

    Returns:
        Partial state update dict.
    """
    return _syllabus_agent(state)
