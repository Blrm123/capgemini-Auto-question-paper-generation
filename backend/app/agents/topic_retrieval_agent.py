"""Refresh question-generation context from structured syllabus topics.

This node makes no LLM call. It delegates to the existing hybrid RAG service,
which preserves FAISS, BM25, reciprocal-rank fusion, and reranking.
"""

from typing import Any

from app.models.state import AgentState
from app.services.logger import log_execution_time, setup_logger

logger = setup_logger(__name__)
AGENT_NAME = "TopicRetrievalAgent"


def topic_retrieval_agent_node(state: AgentState) -> dict[str, Any]:
    """Replace generic context with deduplicated topic-wise evidence."""
    with log_execution_time(logger, AGENT_NAME):
        errors = list(state.get("errors", []))
        if state.get("status") == "failed":
            return {"current_agent": AGENT_NAME, "status": "failed", "errors": errors}

        syllabus_topics = state.get("syllabus_topics", [])
        rag_service = state.get("rag_service")
        if not syllabus_topics:
            error = f"{AGENT_NAME}: Structured syllabus topics are missing."
            logger.error(error)
            errors.append(error)
            return {"content_context": "", "current_agent": AGENT_NAME, "status": "failed", "errors": errors}

        # Keep direct unit tests and external callers that construct a state
        # manually compatible. The normal orchestrator always supplies the
        # service, so production generation always takes the dynamic path.
        if rag_service is None:
            fallback_context = state.get("content_context", "")
            if fallback_context and fallback_context.strip():
                logger.warning(f"{AGENT_NAME}: RAG service unavailable; retaining supplied context.")
                return {
                    "content_context": fallback_context,
                    "topic_retrieval_debug": {"strategy": "prebuilt_context_fallback"},
                    "current_agent": AGENT_NAME,
                    "status": "running",
                    "errors": errors,
                }
            error = f"{AGENT_NAME}: RAG service is missing and no fallback context exists."
            logger.error(error)
            errors.append(error)
            return {"content_context": "", "current_agent": AGENT_NAME, "status": "failed", "errors": errors}

        try:
            result = rag_service.retrieve_for_syllabus_topics(syllabus_topics)
        except Exception as exc:
            error = f"{AGENT_NAME}: Topic-wise retrieval failed — {type(exc).__name__}: {exc}"
            logger.error(error)
            errors.append(error)
            return {"content_context": "", "current_agent": AGENT_NAME, "status": "failed", "errors": errors}

        context = result.get("context", "")
        if not context.strip():
            error = f"{AGENT_NAME}: Topic-wise retrieval returned no context."
            logger.error(error)
            errors.append(error)
            return {"content_context": "", "current_agent": AGENT_NAME, "status": "failed", "errors": errors}

        debug = result.get("debug", {})
        logger.info(
            f"{AGENT_NAME}: Retrieved {debug.get('merged_chunk_count', 0)} unique chunk(s) "
            f"for {debug.get('topics_retrieved', 0)} syllabus topic(s)."
        )
        return {
            "content_context": context,
            "topic_retrieval_debug": debug,
            "current_agent": AGENT_NAME,
            "status": "running",
            "errors": errors,
        }
