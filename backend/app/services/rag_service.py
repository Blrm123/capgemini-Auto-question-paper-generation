"""
services/rag_service.py

Bridge to the RAG chunking and retrieval pipeline.
Uploads are ingested here; retrieved chunks are passed to agentic AI agents.
"""

import os
import sys
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger(__name__)

RAG_DIR = settings.paths.BASE_DIR / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from src.generation.context_builder import format_chunks_for_prompt  # noqa: E402
from src.pipeline.rag_pipeline import RAGPipeline  # noqa: E402

SYLLABUS_RETRIEVAL_QUERY = (
    "syllabus units modules topics course outline curriculum learning objectives"
)
CHUNK_PREVIEW_CHARS = 400
MAX_CHUNKS_IN_DEBUG = 15
TOPIC_RETRIEVAL_TOP_K = int(os.getenv("TOPIC_RETRIEVAL_TOP_K", "2"))
MAX_TOPIC_CONTEXT_CHUNKS = int(os.getenv("MAX_TOPIC_CONTEXT_CHUNKS", "16"))


def chunk_preview(chunk: dict[str, Any], max_chars: int = CHUNK_PREVIEW_CHARS) -> dict[str, Any]:
    """Return a compact chunk representation safe for API/debug responses."""
    content = chunk.get("content", "")
    truncated = len(content) > max_chars
    return {
        "chunk_id": chunk.get("chunk_id"),
        "source": Path(str(chunk.get("source", "?"))).name,
        "first_line": chunk.get("first_line", ""),
        "length": chunk.get("length", len(content)),
        "file_type": chunk.get("file_type", ""),
        "content_preview": content[:max_chars] + ("…" if truncated else ""),
        "truncated": truncated,
    }


class RAGService:
    """Wraps the RAG pipeline for use by the question paper orchestrator."""

    def __init__(self) -> None:
        self._pipeline = RAGPipeline()

    def ingest_files(self, file_paths: list[str]) -> int:
        """
        Ingest one or more documents into a single shared vector index.

        Returns:
            Number of chunks created across all files.
        """
        logger.info(f"RAGService: Ingesting {len(file_paths)} file(s)")
        self._pipeline.ingest_files(file_paths, reset=True)
        chunk_count = len(self._pipeline.all_chunks)
        logger.info(f"RAGService: Ingested {chunk_count} chunk(s) from {len(file_paths)} file(s).")
        return chunk_count

    def ingest_file(self, file_path: str) -> int:
        """Ingest a single file (convenience wrapper)."""
        return self.ingest_files([file_path])

    def retrieve(self, query: str) -> dict[str, Any]:
        """Retrieve reranked chunks for a query."""
        return self._pipeline.retrieve(query)

    def retrieve_for_syllabus_topics(
        self,
        syllabus_topics: list[dict[str, Any]],
        *,
        top_k_per_topic: int = TOPIC_RETRIEVAL_TOP_K,
        max_merged_chunks: int = MAX_TOPIC_CONTEXT_CHUNKS,
    ) -> dict[str, Any]:
        """Retrieve and merge reranked evidence for every extracted topic.

        ``RAGPipeline.retrieve`` remains the only retrieval implementation, so
        dense FAISS search, BM25, RRF, and cross-encoder reranking are kept.
        This method only replaces the old generic content query.
        """
        if top_k_per_topic < 1 or max_merged_chunks < 1:
            raise ValueError("Topic retrieval limits must be at least 1.")

        queries: list[tuple[str, str]] = []
        seen_topics: set[str] = set()
        for unit in syllabus_topics:
            if not isinstance(unit, dict):
                continue
            unit_name = str(unit.get("unit_name", "")).strip()
            for topic in unit.get("topics", []):
                topic_name = str(topic).strip()
                key = topic_name.casefold()
                if not topic_name or key in seen_topics:
                    continue
                seen_topics.add(key)
                queries.append((topic_name, f"{topic_name} {unit_name}".strip()))

        merged: list[dict[str, Any]] = []
        seen_chunks: set[tuple[str, str]] = set()
        retrievals: list[dict[str, Any]] = []
        for topic, query in queries:
            result = self.retrieve(query)
            candidates = (result.get("chunks") or [])[:top_k_per_topic]
            added = 0
            for chunk in candidates:
                source = str(chunk.get("source", ""))
                chunk_id = str(chunk.get("chunk_id", ""))
                chunk_key = (source, chunk_id or str(hash(chunk.get("content", ""))))
                if chunk_key in seen_chunks:
                    continue
                seen_chunks.add(chunk_key)
                merged.append(chunk)
                added += 1
                if len(merged) >= max_merged_chunks:
                    break
            retrievals.append({
                "topic": topic,
                "query": query,
                "returned": len(candidates),
                "added_after_deduplication": added,
                "timings_ms": result.get("debug", {}).get("timings_ms", {}),
            })
            if len(merged) >= max_merged_chunks:
                break

        return {
            "chunks": merged,
            "context": self.format_chunks(merged, exclude_images=False),
            "debug": {
                "strategy": "topic_wise_syllabus_retrieval",
                "topic_count": len(queries),
                "topics_retrieved": len(retrievals),
                "top_k_per_topic": top_k_per_topic,
                "max_merged_chunks": max_merged_chunks,
                "merged_chunk_count": len(merged),
                "retrievals": retrievals,
            },
        }

    def get_all_chunks(self) -> list[dict[str, Any]]:
        """Return all ingested chunks as plain dicts."""
        return self._pipeline.get_all_chunks()

    @staticmethod
    def format_chunks(chunks: list[dict[str, Any]], exclude_images: bool = False) -> str:
        """Format chunk dicts for inclusion in agent prompts."""
        return format_chunks_for_prompt(chunks, exclude_images=exclude_images)

    def _source_files(self, all_chunks: list[dict[str, Any]]) -> list[str]:
        sources = sorted({Path(str(c.get("source", "?"))).name for c in all_chunks})
        return sources

    def build_debug_info(
        self,
        all_chunks: list[dict[str, Any]],
        syllabus_result: dict[str, Any],
        file_count: int = 1,
    ) -> dict[str, Any]:
        """Build a debug payload describing RAG ingestion and retrieval."""
        syllabus_chunks = syllabus_result.get("chunks") or []

        return {
            "file_count": file_count,
            "source_files": self._source_files(all_chunks),
            "total_chunks": len(all_chunks),
            "total_characters": sum(len(c.get("content", "")) for c in all_chunks),
            "syllabus_retrieval": {
                "query": syllabus_result.get("query", SYLLABUS_RETRIEVAL_QUERY),
                "chunks_returned": len(syllabus_chunks),
                "timings_ms": syllabus_result.get("debug", {}).get("timings_ms", {}),
                "chunks_preview": [chunk_preview(c) for c in syllabus_chunks[:MAX_CHUNKS_IN_DEBUG]],
            },
            "content_retrieval": {
                "strategy": "deferred_until_syllabus_topics_exist",
                "chunks_returned": 0,
                "chunks_preview": [],
            },
            "all_chunks_preview": [chunk_preview(c) for c in all_chunks[:MAX_CHUNKS_IN_DEBUG]],
        }

    def preview_files(self, file_paths: list[str]) -> dict[str, Any]:
        """Ingest files and return RAG debug information without running agents."""
        chunk_count = self.ingest_files(file_paths)
        all_chunks = self.get_all_chunks()
        if not all_chunks:
            raise RuntimeError("RAG ingestion produced no chunks from the uploaded file(s).")

        syllabus_result = self.retrieve(SYLLABUS_RETRIEVAL_QUERY)
        return {
            "chunk_count": chunk_count,
            "file_count": len(file_paths),
            "debug": self.build_debug_info(
                all_chunks, syllabus_result, file_count=len(file_paths)
            ),
        }

    def preview_file(self, file_path: str) -> dict[str, Any]:
        """Preview a single file (convenience wrapper)."""
        return self.preview_files([file_path])

    def prepare_agent_contexts(self, file_count: int = 1) -> dict[str, Any]:
        """
        Retrieve and format context strings for downstream agents.

        Returns:
            Dict with rag_chunks, syllabus_context, content_context, and debug.
        """
        all_chunks = self.get_all_chunks()
        if not all_chunks:
            raise RuntimeError("No chunks available after ingestion.")

        syllabus_result = self.retrieve(SYLLABUS_RETRIEVAL_QUERY)
        syllabus_chunks = syllabus_result["chunks"] if syllabus_result["chunks"] else all_chunks[:6]

        return {
            "rag_chunks": all_chunks,
            "syllabus_context": self.format_chunks(syllabus_chunks, exclude_images=True),
            # Used only by the Syllabus Agent's existing recovery path. The
            # TopicRetrievalAgent replaces it before question generation.
            "content_context": self.format_chunks(syllabus_chunks, exclude_images=False),
            "debug": self.build_debug_info(
                all_chunks, syllabus_result, file_count=file_count
            ),
        }
