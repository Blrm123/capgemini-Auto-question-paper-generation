from typing import List
try:
    from langchain.schema import Document
except Exception:
    from langchain_core.documents.base import Document

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except Exception:
    # Minimal fallback splitter if langchain's splitter is unavailable
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size=512, chunk_overlap=50, separators=None, length_function=len):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.separators = separators or ["\n\n\n", "\n\n", "\n"]
            self.length_function = length_function

        def split_documents(self, docs):
            chunks = []
            for doc in docs:
                text = getattr(doc, 'page_content', str(doc))
                start = 0
                L = len(text)
                while start < L:
                    end = min(start + self.chunk_size, L)
                    chunk_text = text[start:end]
                    # create a new Document with same metadata
                    try:
                        new_doc = Document(page_content=chunk_text, metadata=dict(getattr(doc, 'metadata', {}) or {}))
                    except Exception:
                        # Fallback if Document signature differs
                        new_doc = Document(chunk_text)
                        if hasattr(new_doc, 'metadata'):
                            new_doc.metadata.update(getattr(doc, 'metadata', {}) or {})
                    chunks.append(new_doc)
                    start = end - self.chunk_overlap if end - self.chunk_overlap > start else end

            return chunks
from src.utils.config import CHUNK_SIZE, CHUNK_OVERLAP
from src.utils.logger import logger


# Separators ordered from largest semantic unit to smallest
SEPARATORS = ["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


import re

IMAGE_REF_PATTERN = r"\[IMAGE_REF\s+id=([^\s\]]+)\s+path=([^\s\]]+)\](.*?)\[/IMAGE_REF\]"


def chunk_documents(docs: List[Document]) -> List[Document]:
    # 1. Parse and extract all image references from full pages before splitting
    image_map = {}  # img_id -> {"path": path, "explanation": explanation}
    cleaned_docs = []
    
    for doc in docs:
        content = doc.page_content
        # Find all IMAGE_REF matches in the unbroken page content
        for m in re.finditer(IMAGE_REF_PATTERN, content, re.DOTALL):
            img_id = m.group(1).strip()
            img_path = m.group(2).strip()
            img_explanation = m.group(3).strip()
            image_map[img_id] = {
                "path": img_path,
                "explanation": img_explanation
            }
            
        # Clean up the page content, replacing large image tags with a tiny non-splittable marker
        cleaned_content = re.sub(
            IMAGE_REF_PATTERN,
            lambda m: f"\n\n[IMAGE_ID: {m.group(1).strip()}]\n\n",
            content,
            flags=re.DOTALL
        )
        
        cleaned_docs.append(
            Document(
                page_content=cleaned_content,
                metadata=doc.metadata.copy()
            )
        )

    # 2. Split the cleaned documents containing tiny markers
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
        length_function=len,
    )
    chunks = splitter.split_documents(cleaned_docs)

    # Marker pattern to locate and resolve the image IDs in chunks
    MARKER_PATTERN = r"\[IMAGE_ID:\s*([^\s\]]+)\]"

    # 3. Enrich chunk metadata by finding and replacing the tiny markers
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
        
        # Check for image markers in this chunk
        markers = re.findall(MARKER_PATTERN, chunk.page_content)
        if markers:
            # We take the first marker in the chunk to associate with metadata
            img_id = markers[0].strip()
            if img_id in image_map:
                chunk.metadata["image_id"] = img_id
                chunk.metadata["image_path"] = image_map[img_id]["path"]
                chunk.metadata["image_explanation"] = image_map[img_id]["explanation"]
                logger.info(f"Associated image {image_map[img_id]['path']} with chunk {i}")
            
            # Clean up the page content in the chunk, replacing the marker with the final user-friendly description
            resolved_content = re.sub(
                MARKER_PATTERN,
                lambda m: f"\n\n[Image Description: {image_map.get(m.group(1).strip(), {}).get('explanation', '')}]\n\n" if m.group(1).strip() in image_map else "",
                chunk.page_content
            )
            chunk.page_content = resolved_content.strip()

        chunk.metadata["chunk_length"] = len(chunk.page_content)
        # Preserve topic hints if present in content
        lines = chunk.page_content.strip().split("\n")
        if lines:
            chunk.metadata["first_line"] = lines[0][:120]

    logger.info(f"Created {len(chunks)} chunks from {len(docs)} documents")
    return chunks