import os
from pathlib import Path
from typing import List
from langchain_core.documents import Document

from langchain_community.document_loaders import (
    PyMuPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    UnstructuredHTMLLoader,
    CSVLoader,
)
try:
    from src.utils.logger import logger
except ImportError:
    from rag.src.utils.logger import logger


LOADER_MAP = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc": Docx2txtLoader,
    ".txt": TextLoader,
    ".pptx": UnstructuredPowerPointLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls": UnstructuredExcelLoader,
    ".html": UnstructuredHTMLLoader,
    ".htm": UnstructuredHTMLLoader,
    ".csv": CSVLoader,
}


# ---------------------------------------------------------------------------
# Quality filter helpers
# ---------------------------------------------------------------------------

def _is_academic_image(pil_img):
    """
    Multi-heuristic quality gate.
    Returns (is_academic: bool, reason: str).
    A return of (False, reason) means the image should be rejected.
    """
    import numpy as np

    w, h = pil_img.size

    # 1. Reject tiny icons / bullets
    if w < 60 or h < 60:
        return False, f"too small ({w}x{h})"

    # 2. Reject full-page background masks (watermarks etc.)
    if w > 2000 or h > 2800:
        return False, f"full-page background ({w}x{h})"

    # Convert to RGB for consistent analysis
    rgb = pil_img.convert("RGB")
    arr = np.array(rgb)

    # 3. Near-monochrome: very few distinct colors
    # Downsample to 32x32 and count unique colors
    small = rgb.resize((32, 32))
    colors = set(small.getdata())
    if len(colors) < 4:
        return False, f"near-monochrome ({len(colors)} distinct colors)"

    # 4. Stencil/mask: nearly all pixels are pure black or pure white
    flat = arr.reshape(-1, 3)
    black_pixels = ((flat[:, 0] < 15) & (flat[:, 1] < 15) & (flat[:, 2] < 15)).sum()
    white_pixels = ((flat[:, 0] > 240) & (flat[:, 1] > 240) & (flat[:, 2] > 240)).sum()
    total_pixels = flat.shape[0]
    bw_ratio = (black_pixels + white_pixels) / total_pixels
    if bw_ratio > 0.97:
        return False, f"stencil/mask image ({bw_ratio:.2%} black+white)"

    # 5. QR code detection: check for dense uniform grid pattern in a grayscale crop
    gray = pil_img.convert("L")
    gray_arr = np.array(gray)
    # QR codes have very high local variance in a grid pattern
    # Check using block variance on a 64x64 downsampled version
    small_gray = np.array(gray.resize((64, 64)))
    block_size = 8
    block_vars = []
    for row in range(0, 64, block_size):
        for col in range(0, 64, block_size):
            block = small_gray[row:row + block_size, col:col + block_size]
            block_vars.append(float(block.var()))
    avg_block_var = sum(block_vars) / len(block_vars)
    # QR codes have consistently high variance across all blocks
    high_var_blocks = sum(1 for v in block_vars if v > 1000)
    if high_var_blocks > len(block_vars) * 0.5 and avg_block_var > 2000:
        return False, f"QR code pattern (avg block var={avg_block_var:.0f}, high_var_blocks={high_var_blocks})"

    # 6. Barcode detection: tall-and-narrow with horizontal stripe dominance
    aspect = h / w if w > 0 else 1
    if aspect > 3.0 and w < 200:
        return False, f"barcode-like dimensions ({w}x{h}, aspect={aspect:.1f})"

    return True, ""


def _compute_quality_score(pil_img):
    """
    Heuristic quality score 0.0–1.0 for academic content probability.
    Higher = more likely to be a real diagram/figure.
    """
    import numpy as np

    w, h = pil_img.size
    rgb = pil_img.convert("RGB")
    arr = np.array(rgb)

    # More colors = richer content
    small = rgb.resize((64, 64))
    num_colors = len(set(small.getdata()))
    color_score = min(num_colors / 200.0, 1.0)

    # More edge content (diagrams have edges) 
    gray = rgb.convert("L")
    gray_arr = np.array(gray, dtype=float)
    # Simple Sobel-like gradient magnitude
    gy = gray_arr[1:, :] - gray_arr[:-1, :]
    gx = gray_arr[:, 1:] - gray_arr[:, :-1]
    edge_energy = float((gy**2).mean() + (gx**2).mean())
    edge_score = min(edge_energy / 500.0, 1.0)

    # Prefer reasonable aspect ratios (not extreme)
    aspect = max(w, h) / max(min(w, h), 1)
    aspect_score = max(0.0, 1.0 - (aspect - 1.0) / 5.0)

    score = 0.4 * color_score + 0.4 * edge_score + 0.2 * aspect_score
    return round(min(max(score, 0.0), 1.0), 3)


# ---------------------------------------------------------------------------
# Raster image extraction
# ---------------------------------------------------------------------------

def _extract_raster_images(fitz_doc, page, page_num, file_stem, extracted_dir, registry):
    """
    Extract embedded raster image objects from a PDF page.
    Returns list of (image_id, relative_path, caption) tuples for academic images.
    """
    import io
    import fitz
    from PIL import Image as PILImage
    from src.ingestion.image_registry import ImageRecord, make_image_id

    results = []
    image_list = page.get_images(full=True)
    if not image_list:
        return results

    logger.info(f"  Raster: found {len(image_list)} raw image object(s) on page {page_num}")
    saved_count = 0

    for img_info in image_list:
        xref = img_info[0]
        smask_xref = img_info[1]
        width = img_info[2]
        height = img_info[3]

        # Skip soft-masks (they are alpha channels, not content)
        if smask_xref != 0:
            continue

        try:
            pix = fitz.Pixmap(fitz_doc, xref)

            # Skip unicolor or null-colorspace pixmaps
            if pix.is_unicolor or pix.colorspace is None:
                continue

            # Convert non-RGB colorspaces to sRGB
            if pix.n >= 5 or pix.alpha or pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
                pix = fitz.Pixmap(fitz.csRGB, pix)

            img_bytes = pix.tobytes("png")
            pil_img = PILImage.open(io.BytesIO(img_bytes))

            is_academic, reason = _is_academic_image(pil_img)
            quality = _compute_quality_score(pil_img) if is_academic else 0.0

            saved_count += 1
            img_id = make_image_id(file_stem, page_num, saved_count, method="r")
            img_filename = f"{img_id}.png"
            img_save_path = extracted_dir / img_filename
            pil_img.convert("RGB").save(img_save_path, "PNG")

            relative_path = f"uploaded_documents/extracted_images/{img_filename}"
            caption = f"Page {page_num} figure {saved_count}"

            record = ImageRecord(
                image_id=img_id,
                source_file=file_stem,
                page_num=page_num,
                width=pil_img.width,
                height=pil_img.height,
                file_path=str(img_save_path),
                relative_path=relative_path,
                extraction_method="raster",
                quality_score=quality,
                is_academic=is_academic,
                caption=caption,
                filter_reason=reason,
            )
            registry.register(record)

            if is_academic:
                results.append((img_id, relative_path, caption))
                logger.info(f"  Raster: registered academic image {img_id} (quality={quality:.2f})")
            else:
                logger.info(f"  Raster: filtered out {img_id}: {reason}")

        except Exception as img_err:
            logger.error(f"  Raster: failed to extract xref={xref} on page {page_num}: {img_err}")

    return results


# ---------------------------------------------------------------------------
# Vector-diagram detection via page rendering
# ---------------------------------------------------------------------------

def _render_page_vector_figures(fitz_doc, page, page_num, file_stem, extracted_dir, registry):
    """
    Render page to detect vector drawings (graphs, diagrams, geometric figures).
    Only runs if page has >= 5 vector drawings (fast skip for text-only pages).
    Returns list of (image_id, relative_path, caption) tuples for academic crops.
    """
    import io
    import fitz
    from PIL import Image as PILImage
    import numpy as np
    from src.ingestion.image_registry import ImageRecord, make_image_id

    results = []

    # Fast check: only process pages with meaningful vector content
    try:
        drawings = page.get_drawings()
    except Exception:
        return results

    if len(drawings) < 5:
        return results

    logger.info(f"  Vector: page {page_num} has {len(drawings)} drawings — rendering for figure detection")

    try:
        # Render at 150 DPI (matrix scale = 150/72)
        matrix = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        full_page_bytes = pix.tobytes("png")
        full_page_img = PILImage.open(io.BytesIO(full_page_bytes)).convert("RGB")
    except Exception as render_err:
        logger.error(f"  Vector: page render failed on page {page_num}: {render_err}")
        return results

    pw, ph = full_page_img.size
    arr = np.array(full_page_img)

    # Detect non-white rows and columns
    # A pixel is "non-white" if any channel < 230
    non_white = (arr < 230).any(axis=2)

    # Find bounding rows and columns of non-white content clusters
    # Use simple row/column projection to find figure blocks
    row_density = non_white.mean(axis=1)  # fraction of non-white pixels per row
    col_density = non_white.mean(axis=0)

    # Threshold: rows with >10% non-white are "content rows"
    content_rows = (row_density > 0.10).astype(int)
    content_cols = (col_density > 0.10).astype(int)

    # Find contiguous content row blocks
    def find_runs(arr_1d, min_run=30):
        """Find (start, end) of runs of 1s with minimum length."""
        runs = []
        in_run = False
        start = 0
        for i, v in enumerate(arr_1d):
            if v and not in_run:
                start = i
                in_run = True
            elif not v and in_run:
                if i - start >= min_run:
                    runs.append((start, i))
                in_run = False
        if in_run and len(arr_1d) - start >= min_run:
            runs.append((start, len(arr_1d)))
        return runs

    row_runs = find_runs(content_rows, min_run=40)
    col_start = 0
    col_end = pw
    col_runs_list = find_runs(content_cols, min_run=40)
    if col_runs_list:
        col_start = col_runs_list[0][0]
        col_end = col_runs_list[-1][1]

    # For each row block, crop and evaluate
    vector_idx = 0
    for (r_start, r_end) in row_runs:
        crop_h = r_end - r_start
        crop_w = col_end - col_start

        # Skip if crop is too large (full text column) or too small
        if crop_h < 80 or crop_w < 80:
            continue
        # Skip if crop covers more than 60% of page height (likely full text body)
        if crop_h > ph * 0.60:
            continue

        crop = full_page_img.crop((col_start, r_start, col_end, r_end))
        is_academic, reason = _is_academic_image(crop)
        quality = _compute_quality_score(crop) if is_academic else 0.0

        vector_idx += 1
        img_id = make_image_id(file_stem, page_num, vector_idx, method="v")
        img_filename = f"{img_id}.png"
        img_save_path = extracted_dir / img_filename
        crop.save(img_save_path, "PNG")

        relative_path = f"uploaded_documents/extracted_images/{img_filename}"
        caption = f"Page {page_num} vector figure {vector_idx}"

        record = ImageRecord(
            image_id=img_id,
            source_file=file_stem,
            page_num=page_num,
            width=crop.width,
            height=crop.height,
            file_path=str(img_save_path),
            relative_path=relative_path,
            extraction_method="vector_render",
            quality_score=quality,
            is_academic=is_academic,
            caption=caption,
            filter_reason=reason,
        )
        registry.register(record)

        if is_academic:
            results.append((img_id, relative_path, caption))
            logger.info(f"  Vector: registered academic figure {img_id} (quality={quality:.2f})")
        else:
            logger.info(f"  Vector: filtered out crop {img_id}: {reason}")

    return results


# ---------------------------------------------------------------------------
# Main PDF loader
# ---------------------------------------------------------------------------

def load_pdf_with_images(file_path: str) -> List[Document]:
    import fitz
    from src.utils.config import RAG_ROOT
    from src.ingestion.image_registry import ImageRegistry

    try:
        from app.config import settings
        base_dir = settings.paths.BASE_DIR
    except ImportError:
        base_dir = RAG_ROOT.parent if RAG_ROOT.name == "rag" else RAG_ROOT

    extracted_dir = base_dir / "uploaded_documents" / "extracted_images"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    # Initialize and load existing registry
    registry = ImageRegistry(base_dir)
    registry.load()

    fitz_doc = fitz.open(file_path)
    docs = []
    file_stem = Path(file_path).stem

    # Clear stale entries for this source file before re-ingesting
    registry.clear_for_source(file_stem)

    logger.info(f"PDF loader: extracting text and images from {file_path} ({len(fitz_doc)} pages)")

    for page_num_0 in range(len(fitz_doc)):
        page = fitz_doc[page_num_0]
        page_num = page_num_0 + 1
        text = page.get_text()

        # --- Raster image extraction ---
        raster_images = _extract_raster_images(fitz_doc, page, page_num, file_stem, extracted_dir, registry)

        # --- Vector diagram detection ---
        vector_images = _render_page_vector_figures(fitz_doc, page, page_num, file_stem, extracted_dir, registry)

        # Combine; deduplicate by image_id
        all_images = raster_images + vector_images

        # Embed IMAGE_REF markers into page text (only for academic images)
        for img_id, relative_path, caption in all_images:
            text += (
                f"\n\n[IMAGE_REF id={img_id} path={relative_path}]{caption}[/IMAGE_REF]\n\n"
            )

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": file_path,
                    "file_type": ".pdf",
                    "page": page_num,
                }
            )
        )

    # Persist registry after ingestion
    registry.save()
    logger.info(f"PDF loader: {registry.summary()}")

    return docs


def load_document(file_path: str) -> List[Document]:
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        try:
            docs = load_pdf_with_images(file_path)
            logger.info(f"Loaded {len(docs)} pages with custom PDF loader from {file_path}")
            return docs
        except Exception as e:
            logger.error(f"Custom PDF loader failed: {e}. Falling back to default PyMuPDFLoader.")

    loader_cls = LOADER_MAP.get(ext)
    if not loader_cls:
        logger.warning(f"Unsupported file type: {ext} for file {file_path}")
        return []
    try:
        loader = loader_cls(file_path)
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = file_path
            doc.metadata["file_type"] = ext
        logger.info(f"Loaded {len(docs)} pages/sections from {file_path}")
        return docs
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return []


def load_directory(dir_path: str) -> List[Document]:
    all_docs = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            full_path = os.path.join(root, file)
            docs = load_document(full_path)
            all_docs.extend(docs)
    logger.info(f"Total documents loaded from directory: {len(all_docs)}")
    return all_docs
