import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image as PILImage

# Import Document structure
try:
    from langchain.schema import Document
except ImportError:
    from langchain_core.documents.base import Document

from src.ingestion.loader import load_document
from src.ingestion.chunker import chunk_documents
from src.generation.context_builder import document_to_chunk_dict
from src.utils.config import RAG_ROOT

TEST_DIR = Path(__file__).resolve().parent / "temp_test_data"
TEST_PDF_PATH = TEST_DIR / "test_notes_with_image.pdf"
TEST_IMG_PATH = TEST_DIR / "sample_chart.png"


@pytest.fixture(scope="module", autouse=True)
def setup_temp_data():
    """Create a temporary PDF containing an image for extraction tests."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Create a structured dummy diagram image with edges and colors
    img = PILImage.new("RGB", (300, 300), color="white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for i in range(0, 300, 15):
        draw.line([(i, 0), (300 - i, 300)], fill=((i * 7) % 255, 100, (i * 3) % 255), width=2)
        draw.rectangle([(i, i), (min(i + 20, 299), min(i + 20, 299))], outline=(50, 200, (i * 5) % 255))
    img.save(TEST_IMG_PATH)
    
    # 2. Draw a PDF with this image using reportlab
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(TEST_PDF_PATH))
    c.drawString(100, 750, "Here is a note about IoT Protocols:")
    c.drawString(100, 730, "The diagram below shows the MQTT publish-subscribe mechanism.")
    c.drawImage(str(TEST_IMG_PATH), 100, 500, width=100, height=100)
    c.drawString(100, 480, "End of MQTT Section.")
    c.showPage()
    c.save()
    
    yield
    
    # Cleanup temp test files
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
        
    # Cleanup extracted images directory for this test if it gets populated
    backend_root = RAG_ROOT.parent if RAG_ROOT.name == "rag" else RAG_ROOT
    extracted_dir = backend_root / "uploaded_documents" / "extracted_images"
    test_extracted_imgs = list(extracted_dir.glob("test_notes_with_image_p1_img*.png"))
    for file in test_extracted_imgs:
        try:
            file.unlink()
        except OSError:
            pass


@patch("app.services.llm_service.LLMService")
@patch("sentence_transformers.SentenceTransformer")
def test_image_extraction_and_rag_indexing(mock_clip_class, mock_llm_class):
    """Test that PDF loader extracts images with placeholders, and ImageDescriptorAgent ranks and annotates them."""
    # Force USE_VISION_MODEL to True for test execution so it doesn't depend on local .env
    try:
        from app.config import settings
        original_use_vision = settings.llm.USE_VISION_MODEL
        settings.llm.USE_VISION_MODEL = True
    except ImportError:
        original_use_vision = True
        settings = None

    # Mock LLMService
    mock_llm_instance = MagicMock()
    mock_llm_instance.describe_image.return_value = "A diagram showing the MQTT publish-subscribe flow."
    mock_llm_class.return_value = mock_llm_instance

    # Mock CLIP Model
    mock_clip_instance = MagicMock()
    import torch
    # Mock model.encode to return dummy tensors of ones
    mock_clip_instance.encode.side_effect = lambda inputs, **kwargs: (
        torch.ones((len(inputs), 384)) if isinstance(inputs, list) else torch.ones((1, 384))
    )
    mock_clip_class.return_value = mock_clip_instance
    
    # 1. Load document (image extraction happens, but vision description is deferred/placeholder)
    try:
        docs = load_document(str(TEST_PDF_PATH))
    finally:
        # Restore original value
        if settings is not None:
            settings.llm.USE_VISION_MODEL = original_use_vision
    
    assert len(docs) == 1
    page_content = docs[0].page_content
    
    # Verify the image ref tag is embedded in page content with placeholder description
    assert "[IMAGE_REF id=test_notes_with_image_p1_r1" in page_content
    assert "path=uploaded_documents/extracted_images/test_notes_with_image_p1_r1.png" in page_content
    
    # Check that the image file actually got written to the backend directory
    backend_root = RAG_ROOT.parent if RAG_ROOT.name == "rag" else RAG_ROOT
    extracted_img = backend_root / "uploaded_documents" / "extracted_images" / "test_notes_with_image_p1_r1.png"
    assert extracted_img.is_file(), f"Extracted image not found at {extracted_img}"
    
    # 2. Chunk documents and verify metadata placeholder
    chunks = chunk_documents(docs)
    
    # Find the chunk containing the image reference
    image_chunks = [c for c in chunks if c.metadata.get("image_path") is not None]
    assert len(image_chunks) > 0
    
    target_chunk = image_chunks[0]
    assert target_chunk.metadata["image_id"] == "test_notes_with_image_p1_r1"
    assert target_chunk.metadata["image_path"] == "uploaded_documents/extracted_images/test_notes_with_image_p1_r1.png"
    
    # Verify the raw tag is cleaned up from page_content and replaced with placeholder format
    assert "[IMAGE_REF" not in target_chunk.page_content

    # 3. Build state and run ImageDescriptorAgent
    from app.models.state import AgentState
    from app.agents.image_descriptor_agent import image_descriptor_agent_node
    from src.generation.context_builder import document_to_chunk_dict, format_chunks_for_prompt

    chunk_dicts = [document_to_chunk_dict(c) for c in chunks]
    
    initial_state = AgentState(
        rag_chunks=chunk_dicts,
        syllabus_context="Syllabus Unit 1: IoT protocols, MQTT, publish-subscribe",
        content_context=format_chunks_for_prompt(chunk_dicts, exclude_images=False),
        syllabus_topics=[
            {
                "unit_number": 1,
                "unit_name": "IoT protocols",
                "topics": ["MQTT Protocol", "Publish-Subscribe model"]
            }
        ],
        question_distribution={
            "total_marks": 10,
            "two_mark_questions": 5,
            "five_mark_questions": 0,
            "ten_mark_questions": 0,
            "fifteen_mark_questions": 0,
            "easy_percentage": 100,
            "medium_percentage": 0,
            "hard_percentage": 0,
        },
        generated_questions=[],
        bloom_analysis=[],
        validated_questions=[],
        answer_key=[],
        paper_metadata=None,
        final_pdf_path=None,
        answer_key_pdf_path=None,
        errors=[],
        current_agent=None,
        status="running",
    )

    # Invoke the agent node
    updated_state = image_descriptor_agent_node(initial_state)

    # Check updated chunks and context
    updated_chunk_dicts = updated_state["rag_chunks"]
    updated_image_chunks = [c for c in updated_chunk_dicts if c.get("image_path") is not None]
    assert len(updated_image_chunks) > 0
    assert updated_image_chunks[0]["image_explanation"] == "A diagram showing the MQTT publish-subscribe flow."
    assert "[Image Description: A diagram showing the MQTT publish-subscribe flow.]" in updated_image_chunks[0]["content"]

    # Verify content_context has updated description
    assert "[Image Description: A diagram showing the MQTT publish-subscribe flow.]" in updated_state["content_context"]
    assert "[Image Description: Page 1 figure 1]" not in updated_state["content_context"]
