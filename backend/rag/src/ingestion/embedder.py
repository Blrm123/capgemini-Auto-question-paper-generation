import os
import pickle
from typing import List, Optional

from langchain_core.documents.base import Document

from src.utils.config import EMBEDDING_MODEL, FAISS_INDEX_PATH
from src.utils.logger import logger

_DUMMY_DOCS_FILE = "dummy_docs.pkl"

_HF_LIBS_AVAILABLE = False
try:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_pinecone import PineconeVectorStore
    _HF_LIBS_AVAILABLE = True
except Exception as e:
    import traceback
    logger.error(f"Failed to import HF/Pinecone libs: {e}\n{traceback.format_exc()}")
    FAISS = None  # type: ignore
    HuggingFaceEmbeddings = None  # type: ignore
    PineconeVectorStore = None # type: ignore


class DummyVectorStore:
    """Token-overlap fallback when HuggingFace embeddings are unavailable."""
    def __init__(self, docs: Optional[List[Document]] = None):
        self.docs = docs or []
        self._token_sets = [set(d.page_content.lower().split()) for d in self.docs]
        self.docstore = type("docstore", (), {"_dict": {i: d for i, d in enumerate(self.docs)}})()

    @classmethod
    def from_documents(cls, docs: List[Document], embedder=None):
        return cls(docs)

    def save_local(self, path: str):
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, _DUMMY_DOCS_FILE), "wb") as f:
            pickle.dump(self.docs, f)

    @classmethod
    def load_local(cls, path: str, embedder=None, allow_dangerous_deserialization=False):
        docs_path = os.path.join(path, _DUMMY_DOCS_FILE)
        if not os.path.exists(docs_path):
            raise FileNotFoundError(f"No dummy index found at {docs_path}")
        with open(docs_path, "rb") as f:
            docs = pickle.load(f)
        return cls(docs)

    def add_documents(self, new_docs: List[Document]):
        start = len(self.docs)
        self.docs.extend(new_docs)
        self._token_sets.extend([set(d.page_content.lower().split()) for d in new_docs])
        for i, d in enumerate(new_docs, start=start):
            self.docstore._dict[i] = d

    def similarity_search_with_score(self, query: str, k: int = 5):
        qset = set(query.lower().split())
        scores = []
        for d_set, doc in zip(self._token_sets, self.docs):
            inter = len(qset & d_set)
            score = inter / (1 + len(d_set))
            scores.append((doc, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


def _get_embedder():
    if not _HF_LIBS_AVAILABLE or HuggingFaceEmbeddings is None:
        raise ImportError("langchain-huggingface is not installed")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

def _get_pinecone_index_name():
    return os.environ.get("PINECONE_INDEX_NAME", "qp-generator")

def build_vector_index(chunks: List[Document], force_local: bool = False):
    """Builds Pinecone index if configured, otherwise falls back to FAISS."""
    logger.info("Building vector index...")
    
    if not _HF_LIBS_AVAILABLE:
        logger.warning("Using token-overlap fallback index (install sentence-transformers for full embeddings).")
        vs = DummyVectorStore.from_documents(chunks)
        os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
        vs.save_local(FAISS_INDEX_PATH)
        return vs
        
    embedder = _get_embedder()
    
    if not force_local and os.environ.get("PINECONE_API_KEY"):
        logger.info("Uploading to Pinecone...")
        try:
            vectorstore = PineconeVectorStore.from_documents(
                chunks, embedder, index_name=_get_pinecone_index_name()
            )
            logger.info("Pinecone upload complete.")
            return vectorstore
        except Exception as exc:
            logger.warning(f"Pinecone embedding failed: {exc}, falling back to FAISS.")
            
    # Fallback FAISS
    try:
        vectorstore = FAISS.from_documents(chunks, embedder)
        os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
        vectorstore.save_local(FAISS_INDEX_PATH)
        logger.info(f"FAISS index saved to {FAISS_INDEX_PATH}")
        return vectorstore
    except Exception as exc:
        logger.warning(f"FAISS embedding build failed: {exc}")
        return DummyVectorStore.from_documents(chunks)

def load_vector_index():
    """Load Pinecone index if configured, otherwise FAISS."""
    if os.environ.get("PINECONE_API_KEY") and _HF_LIBS_AVAILABLE:
        logger.info("Connecting to Pinecone index...")
        return PineconeVectorStore(index_name=_get_pinecone_index_name(), embedding=_get_embedder())
        
    if _HF_LIBS_AVAILABLE and FAISS is not None:
        try:
            return FAISS.load_local(
                FAISS_INDEX_PATH, _get_embedder(), allow_dangerous_deserialization=True
            )
        except Exception:
            pass
    return DummyVectorStore.load_local(FAISS_INDEX_PATH)
