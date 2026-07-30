"""
workflows/langgraph_workflow.py

LangGraph Workflow for the Agentic Question Paper Generator.

Workflow Order (FIXED: SyllabusAgent runs first so ImageDescriptorAgent
has real topic names available for Gemini vision context):

    START
      -> syllabus_agent           (extract structured topics)
      -> image_descriptor_agent   (Gemini vision: describe images using real topics)
      -> topic_retrieval_agent    (refresh RAG context per topic)
      -> question_generator_agent (generate questions + image-based questions)
      -> bloom_agent              (Bloom taxonomy tagging)
      -> validation_agent         (structural quality validation)
      -> answerkey_agent          (generate answer key)
      -> END

Error Routing:
    After each agent, if state["status"] == "failed",
    the workflow routes directly to END to stop further execution.
"""

from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph

from app.agents.answerkey_agent import answerkey_agent_node
from app.agents.bloom_agent import bloom_agent_node
from app.agents.image_descriptor_agent import image_descriptor_agent_node
from app.agents.question_generator_agent import question_generator_agent_node
from app.agents.syllabus_agent import syllabus_agent_node
from app.agents.topic_retrieval_agent import topic_retrieval_agent_node
from app.agents.validation_agent import validation_agent_node
from app.models.state import AgentState, PaperMetadata, QuestionDistribution, RagChunk
from app.services.logger import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Node name constants - single source of truth for graph wiring
# ---------------------------------------------------------------------------
NODE_SYLLABUS = "syllabus_agent"
NODE_IMAGE_DESCRIPTOR = "image_descriptor_agent"
NODE_TOPIC_RETRIEVAL = "topic_retrieval_agent"
NODE_QUESTION = "question_generator_agent"
NODE_BLOOM = "bloom_agent"
NODE_VALIDATION = "validation_agent"
NODE_ANSWERKEY = "answerkey_agent"


# ---------------------------------------------------------------------------
# Conditional routing function
# ---------------------------------------------------------------------------

def _route_after_agent(state: AgentState) -> str:
    """
    Routing function used after every agent node.

    Returns:
        "failed": route to END immediately if the agent failed.
        "ok":     continue to the next agent node.
    """
    if state.get("status") == "failed":
        logger.warning(
            f"Workflow routing: status is 'failed' after "
            f"'{state.get('current_agent', 'unknown')}'. Terminating early."
        )
        return "failed"
    return "ok"


# ---------------------------------------------------------------------------
# Workflow factory
# ---------------------------------------------------------------------------

def create_workflow() -> Any:
    """
    Build and compile the LangGraph StateGraph.

    Order: SyllabusAgent -> ImageDescriptorAgent -> TopicRetrievalAgent
           -> QuestionGeneratorAgent -> BloomAgent -> ValidationAgent -> AnswerKeyAgent

    SyllabusAgent runs FIRST so ImageDescriptorAgent receives real syllabus
    topics for Gemini vision context.

    Returns:
        A compiled LangGraph CompiledStateGraph ready to invoke.
    """
    logger.info("Building LangGraph workflow...")

    graph = StateGraph(AgentState)

    # ---- Register nodes ----
    graph.add_node(NODE_SYLLABUS,          syllabus_agent_node)
    graph.add_node(NODE_IMAGE_DESCRIPTOR,  image_descriptor_agent_node)
    graph.add_node(NODE_TOPIC_RETRIEVAL,   topic_retrieval_agent_node)
    graph.add_node(NODE_QUESTION,          question_generator_agent_node)
    graph.add_node(NODE_BLOOM,             bloom_agent_node)
    graph.add_node(NODE_VALIDATION,        validation_agent_node)
    graph.add_node(NODE_ANSWERKEY,         answerkey_agent_node)

    # ---- Entry point: SyllabusAgent runs FIRST ----
    graph.set_entry_point(NODE_SYLLABUS)

    # ---- Conditional edges: continue or stop after each agent ----
    graph.add_conditional_edges(
        NODE_SYLLABUS,
        _route_after_agent,
        {"ok": NODE_IMAGE_DESCRIPTOR, "failed": END},
    )
    graph.add_conditional_edges(
        NODE_IMAGE_DESCRIPTOR,
        _route_after_agent,
        {"ok": NODE_TOPIC_RETRIEVAL, "failed": END},
    )
    graph.add_conditional_edges(
        NODE_TOPIC_RETRIEVAL,
        _route_after_agent,
        {"ok": NODE_QUESTION, "failed": END},
    )
    graph.add_conditional_edges(
        NODE_QUESTION,
        _route_after_agent,
        {"ok": NODE_BLOOM, "failed": END},
    )
    graph.add_conditional_edges(
        NODE_BLOOM,
        _route_after_agent,
        {"ok": NODE_VALIDATION, "failed": END},
    )
    graph.add_conditional_edges(
        NODE_VALIDATION,
        _route_after_agent,
        {"ok": NODE_ANSWERKEY, "failed": END},
    )

    # ---- Final node always routes to END ----
    graph.add_edge(NODE_ANSWERKEY, END)

    compiled = graph.compile()
    logger.info("LangGraph workflow compiled successfully.")
    return compiled


# ---------------------------------------------------------------------------
# Initial state builder
# ---------------------------------------------------------------------------

def build_initial_state(
    rag_chunks: List[RagChunk],
    syllabus_context: str,
    content_context: str,
    distribution: QuestionDistribution,
    paper_metadata: Optional[PaperMetadata] = None,
    rag_service: Any = None,
) -> AgentState:
    """
    Construct a fully-initialised AgentState dict to pass to the workflow.

    Args:
        rag_chunks:         All document chunks from RAG ingestion.
        syllabus_context:   Formatted retrieved chunks for syllabus extraction.
        content_context:    Formatted retrieved chunks for question generation.
        distribution:       Question distribution parameters (marks, counts, difficulty).
        paper_metadata:     Optional PDF header metadata (institution, course, etc.).
        rag_service:        In-memory RAG service for topic-wise retrieval.

    Returns:
        A complete AgentState dict ready to invoke the compiled workflow.
    """
    subject: Optional[str] = None
    if paper_metadata and isinstance(paper_metadata, dict):
        subject = paper_metadata.get("course_name") or None

    return AgentState(
        rag_chunks=rag_chunks,
        syllabus_context=syllabus_context,
        content_context=content_context,
        rag_service=rag_service,
        topic_retrieval_debug={},
        syllabus_topics=[],
        image_topic_map={},
        question_distribution=distribution,
        generated_questions=[],
        bloom_analysis=[],
        validated_questions=[],
        answer_key=[],
        paper_metadata=paper_metadata,
        final_pdf_path=None,
        answer_key_pdf_path=None,
        errors=[],
        current_agent=None,
        status="initialized",
        subject=subject,
    )
