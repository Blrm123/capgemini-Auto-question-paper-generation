import os
import shutil
from typing import List, Optional, Dict, Any

from langchain_core.documents.base import Document
import time
from src.generation.context_builder import document_to_chunk_dict
from src.ingestion.chunker import chunk_documents
from src.ingestion.embedder import build_vector_index, load_vector_index
from src.ingestion.loader import load_document, load_directory
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.retriever import HybridRetriever
from src.utils.config import FAISS_INDEX_PATH
from src.utils.logger import logger


class RAGPipeline:
    """Chunking, embedding, and retrieval pipeline for persistent Vector DB."""

    def __init__(self):
        self.vectorstore = None
        self.all_chunks: List[Document] = []
        self.retriever: Optional[HybridRetriever] = None
        self.reranker = CrossEncoderReranker()
        self.load()

    def reset(self) -> None:
        """Clear in-memory state and the persisted FAISS index. (Does NOT clear Pinecone)"""
        if os.path.exists(FAISS_INDEX_PATH):
            shutil.rmtree(FAISS_INDEX_PATH)
        self.vectorstore = None
        self.all_chunks = []
        self.retriever = None
        logger.info("RAG local index reset.")

    def ingest_files(self, file_paths: List[str], reset: bool = True) -> int:
        """Convenience method to ingest files without additional metadata."""
        if reset:
            self.reset()
        return self.ingest_files_with_metadata(file_paths, metadata={})

    def ingest_files_with_metadata(self, file_paths: List[str], metadata: Dict[str, Any]) -> int:
        """Ingest files and append them to the existing persistent vector store with metadata."""
        all_docs: List[Document] = []
        for file_path in file_paths:
            docs = load_document(file_path)
            if docs:
                for doc in docs:
                    # Update Langchain Document metadata
                    doc.metadata.update(metadata)
                all_docs.extend(docs)
            else:
                logger.warning(f"No content loaded from {file_path}")

        if not all_docs:
            logger.warning("No documents loaded from any file.")
            return 0

        chunks = chunk_documents(all_docs)
        self.all_chunks.extend(chunks)
        
        is_ad_hoc = not metadata
        
        is_pinecone_active = self.vectorstore and self.vectorstore.__class__.__name__ == "PineconeVectorStore"

        if is_ad_hoc or not os.environ.get("PINECONE_API_KEY") or not is_pinecone_active:
            # We must rebuild if it's ad-hoc (forces local FAISS), or if we have no API key,
            # or if the current vectorstore is NOT Pinecone but we are trying to do a KB upload.
            if is_ad_hoc:
                logger.info("Ad-hoc generation detected: Building local FAISS index instead of polluting Pinecone.")
            else:
                logger.info("KB upload detected but Pinecone is not currently active. Building index...")
            self.vectorstore = build_vector_index(self.all_chunks, force_local=is_ad_hoc)
        else:
            # Persistent Knowledge Base insertion and Pinecone is active - seamlessly add
            self.vectorstore.add_documents(chunks)
            
        self.retriever = HybridRetriever(self.vectorstore, self.all_chunks)
        logger.info(f"Ingested {len(chunks)} chunks into vector store.")
        return len(chunks)

    def load(self):
        """Load existing vector index (Pinecone or FAISS)."""
        self.vectorstore = load_vector_index()
        # For Pinecone, we might not have all_chunks in memory. That's okay, BM25 fallback is disabled or limited.
        try:
            self.all_chunks = list(self.vectorstore.docstore._dict.values())
        except AttributeError:
            self.all_chunks = [] # Pinecone doesn't have a local docstore dict
            
        self.retriever = HybridRetriever(self.vectorstore, self.all_chunks)
        logger.info("Loaded vector index")

    def retrieve(self, query: str, filters: Optional[Dict[str, Any]] = None, verbose: bool = False) -> dict:
        """Retrieve chunks for a given query, optionally applying metadata filters."""
        if not self.retriever:
            self.load()
            
        if not self.retriever:
            logger.warning("Retrieval attempted but no vectorstore loaded.")
            return {"query": query, "top_chunks": [], "debug": {}}
            
        # Temporarily store filters on the retriever if needed, 
        # or we update HybridRetriever to accept filters.
        # We will pass filters directly to vectorstore search for now.
        
        start_time = time.time()
        
        # 1. Vector Search
        search_kwargs = {"k": 15}
        if filters and os.environ.get("PINECONE_API_KEY"):
            # Pinecone metadata filtering
            search_kwargs["filter"] = filters
            
        try:
            vs_results = self.vectorstore.similarity_search_with_score(query, **search_kwargs)
            vs_docs = [doc for doc, _score in vs_results]
        except Exception as exc:
            logger.error(f"Vector search failed: {exc}")
            vs_docs = []
            
        # We skip BM25 here if using Pinecone because we don't have all chunks in memory easily.
        # Just use Vector Search + Reranker
        unique_docs = {d.page_content: d for d in vs_docs}.values()
        
        # 2. Rerank
        try:
            reranked_docs = self.reranker.rerank(query, list(unique_docs), top_n=8)
        except Exception as exc:
            logger.warning(f"Reranker failed ({exc}). Using un-reranked vector results.")
            reranked_docs = list(unique_docs)[:8]
            
        chunks = [document_to_chunk_dict(d) for d in reranked_docs]
        
        debug_info = {
            "query": query,
            "filters_applied": filters,
            "retrieval_time_ms": int((time.time() - start_time) * 1000),
            "vector_search_hits": len(vs_docs)
        }
        
        return {"query": query, "top_chunks": chunks, "debug": debug_info}

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Return all ingested chunks as plain dicts."""
        return [document_to_chunk_dict(d) for d in self.all_chunks]
