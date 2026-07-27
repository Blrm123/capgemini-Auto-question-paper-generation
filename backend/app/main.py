"""
main.py

FastAPI application entry point for the Agentic Question Paper Generator.

Endpoints:
  POST /generate         — Upload syllabus + parameters → RAG ingest → agents → PDF paths
  GET  /papers           — List all generated PDFs in generated_papers/
  GET  /download/{name}  — Download a generated PDF by filename
  GET  /health           — Health check

The Orchestrator is created once at startup via the lifespan context manager
and shared across all requests.
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from oauthlib.oauth2 import OAuth2Error
from pydantic import BaseModel, Field

from app.agents.orchestrator import Orchestrator, OrchestratorResult
from app.config import settings
from app.models.state import PaperMetadata, QuestionDistribution
from app.services.logger import setup_logger
from app.services.rag_service import RAGService
from integrations.google_auth import GoogleOAuthStore
from integrations.google_sources import (
    download_selection,
    list_classroom_courses,
    list_classroom_materials,
    list_drive_folder,
)

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan — creates the Orchestrator singleton
# ---------------------------------------------------------------------------

_orchestrator: Optional[Orchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Startup:  instantiate Orchestrator (validates API key, creates dirs)
    Shutdown: log cleanup message
    """
    global _orchestrator
    logger.info("Application starting up...")
    _orchestrator = Orchestrator()
    logger.info("Application ready to serve requests.")
    yield
    logger.info("Application shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.api.TITLE,
    description=settings.api.DESCRIPTION,
    version=settings.api.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class GenerateResponse(BaseModel):
    """Response body for the /generate endpoint."""
    success: bool
    message: str
    final_pdf_path: Optional[str] = None
    answer_key_pdf_path: Optional[str] = None
    elapsed_seconds: float
    rag_chunk_count: int = 0
    errors: list[str] = Field(default_factory=list)
    debug: dict = Field(default_factory=dict)
    questions: Optional[list[dict]] = None
    answer_key: Optional[list[dict]] = None


class PaperMetadataModel(BaseModel):
    institution_name: str
    course_name: str
    course_code: str
    semester: str
    exam_type: str
    duration: str
    maximum_marks: int
    date: Optional[str] = None


class PrintPdfRequest(BaseModel):
    questions: list[dict]
    answer_key: list[dict]
    paper_metadata: PaperMetadataModel


class UpdateAnswerKeyRequest(BaseModel):
    """Edited questions whose answer-key entries need to be regenerated."""
    questions: list[dict]
    answer_key: list[dict]
    modified_question_ids: list[str]


class RagPreviewResponse(BaseModel):
    """Response body for the /rag/preview endpoint."""
    success: bool
    message: str
    file_names: list[str] = Field(default_factory=list)
    file_count: int = 0
    total_size_mb: float = 0.0
    chunk_count: int = 0
    debug: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class PaperListResponse(BaseModel):
    """Response body for the /papers endpoint."""
    total: int
    files: list[str]


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""
    status: str
    version: str
    model: str
    max_upload_size_mb: int


class GoogleAuthResponse(BaseModel):
    authorization_url: str
    session_id: str


class GoogleItem(BaseModel):
    id: str
    name: str
    mime_type: Optional[str] = None
    modified_time: Optional[str] = None
    size: int = 0
    kind: Optional[str] = None
    supported: Optional[bool] = None
    source: Optional[str] = None


def _google_oauth() -> GoogleOAuthStore:
    return GoogleOAuthStore(
        settings.google.CLIENT_SECRET_FILE,
        settings.google.REDIRECT_URI,
        settings.paths.GOOGLE_STATE_DIR,
    )


def _google_creds(session_id: str):
    try:
        return _google_oauth().credentials(session_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def _json_id_list(value: Optional[str], field_name: str) -> list[str]:
    if not value:
        return []
    import json
    try:
        ids = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON array.") from exc
    if not isinstance(ids, list) or not all(isinstance(item, str) and item for item in ids):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON array of IDs.")
    return ids


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check — confirms the service is running."""
    return HealthResponse(
        status="ok",
        version=settings.api.VERSION,
        model=settings.llm.MODEL_NAME,
        max_upload_size_mb=settings.api.MAX_UPLOAD_SIZE_MB,
    )


@app.post("/google/oauth/start", response_model=GoogleAuthResponse, tags=["Google"])
async def google_oauth_start() -> GoogleAuthResponse:
    """Start OAuth; the browser should navigate to the returned Google URL."""
    try:
        authorization_url, session_id = _google_oauth().begin()
        return GoogleAuthResponse(authorization_url=authorization_url, session_id=session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/google/oauth/callback", tags=["Google"])
async def google_oauth_callback(state: str, code: Optional[str] = None, error: Optional[str] = None):
    if error:
        return RedirectResponse(f"{settings.google.FRONTEND_REDIRECT_URI}?google_error={error}")
    if not code:
        raise HTTPException(status_code=400, detail="Google did not return an authorization code.")
    try:
        session_id = _google_oauth().complete(state, code)
    except (RuntimeError, ValueError, OAuth2Error) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from urllib.parse import urlencode
    return RedirectResponse(f"{settings.google.FRONTEND_REDIRECT_URI}?{urlencode({'google_connected': session_id})}")


@app.get("/google/drive/folders/{folder_id}/items", response_model=list[GoogleItem], tags=["Google"])
async def google_drive_items(folder_id: str, session_id: str) -> list[dict]:
    try:
        return list_drive_folder(_google_creds(session_id), folder_id)
    except Exception as exc:
        logger.warning("Could not browse Google Drive: %s", exc)
        raise HTTPException(status_code=400, detail=f"Could not browse Google Drive: {exc}") from exc


@app.get("/google/classroom/courses", response_model=list[GoogleItem], tags=["Google"])
async def google_classroom_courses(session_id: str) -> list[dict]:
    try:
        return list_classroom_courses(_google_creds(session_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load Google Classroom courses: {exc}") from exc


@app.get("/google/classroom/courses/{course_id}/materials", response_model=list[GoogleItem], tags=["Google"])
async def google_classroom_course_materials(course_id: str, session_id: str) -> list[dict]:
    try:
        return list_classroom_materials(_google_creds(session_id), course_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load Classroom materials: {exc}") from exc


def _mime_for_extension(extension: str) -> str:
    return {
        "pdf": "application/pdf",
        "txt": "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(extension, "application/octet-stream")


async def _save_and_validate_uploads(
    files: list[UploadFile],
) -> tuple[list[str], list[str], float, list[Path]]:
    """Read, validate, and persist uploaded files. Returns names, paths, total MB."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. Please upload at least one document.",
        )

    saved_names: list[str] = []
    saved_paths: list[Path] = []
    total_size_mb = 0.0

    for file in files:
        filename = file.filename or ""
        extension = Path(filename).suffix.lstrip(".").lower()

        if extension not in settings.api.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported file type '.{extension}' in '{filename}'. "
                    f"Allowed: {settings.api.ALLOWED_EXTENSIONS}"
                ),
            )

        file_bytes = await file.read()
        size_mb = len(file_bytes) / (1024 * 1024)
        total_size_mb += size_mb

        if size_mb > settings.api.MAX_UPLOAD_SIZE_MB:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File '{filename}' is {size_mb:.1f} MB — exceeds per-file limit of "
                    f"{settings.api.MAX_UPLOAD_SIZE_MB} MB."
                ),
            )

        safe_name = Path(filename).name or f"upload_{uuid4().hex}.{extension}"
        upload_path = settings.paths.UPLOADED_DOCUMENTS_DIR / safe_name
        upload_path.write_bytes(file_bytes)
        saved_names.append(safe_name)
        saved_paths.append(upload_path)

    return saved_names, [str(p) for p in saved_paths], total_size_mb, saved_paths


@app.post(
    "/rag/preview",
    response_model=RagPreviewResponse,
    tags=["Debug"],
    summary="Preview RAG chunking for an uploaded file (no generation)",
)
async def rag_preview(
    files: Annotated[list[UploadFile], File(description="Syllabus/course documents to preview")],
) -> RagPreviewResponse:
    """
    Run RAG ingestion only and return chunk/debug information.
    Useful for validating uploads before running the full agent pipeline.
    """
    try:
        file_names, upload_paths, total_size_mb, _paths = await _save_and_validate_uploads(files)
    except HTTPException:
        raise

    logger.info(f"RAG preview for {len(file_names)} file(s) ({total_size_mb:.2f} MB total)")

    try:
        rag_service = RAGService()
        preview = rag_service.preview_files(upload_paths)
        return RagPreviewResponse(
            success=True,
            message=(
                f"RAG preview complete — {preview['chunk_count']} chunk(s) "
                f"from {preview['file_count']} file(s)."
            ),
            file_names=file_names,
            file_count=preview["file_count"],
            total_size_mb=round(total_size_mb, 2),
            chunk_count=preview["chunk_count"],
            debug=preview["debug"],
        )
    except Exception as exc:
        logger.error(f"RAG preview failed: {exc}")
        return RagPreviewResponse(
            success=False,
            message=f"RAG preview failed: {exc}",
            file_names=file_names,
            file_count=len(file_names),
            total_size_mb=round(total_size_mb, 2),
            errors=[str(exc)],
        )


@app.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Generation"],
    summary="Upload syllabus and generate question paper",
)
async def generate_question_paper(
    # --- File upload (one or more documents) ---
    files: Annotated[Optional[list[UploadFile]], File(description="Syllabus/course PDF, TXT, DOCX, or XLSX files")] = None,
    google_session_id: Annotated[Optional[str], Form()] = None,
    google_file_ids: Annotated[Optional[str], Form(description="JSON array of selected Drive/Classroom file IDs")] = None,
    google_folder_ids: Annotated[Optional[str], Form(description="JSON array of selected Drive folder IDs")] = None,

    # --- Question distribution (Form fields) ---
    total_marks: Annotated[int, Form(description="Total marks for the paper")] = 100,
    two_mark_questions: Annotated[int, Form(description="Number of 2-mark questions")] = 5,
    five_mark_questions: Annotated[int, Form(description="Number of 5-mark questions")] = 4,
    ten_mark_questions: Annotated[int, Form(description="Number of 10-mark questions")] = 3,
    fifteen_mark_questions: Annotated[int, Form(description="Number of 15-mark questions")] = 2,
    easy_percentage: Annotated[int, Form(description="% of easy questions (0-100)")] = 30,
    medium_percentage: Annotated[int, Form(description="% of medium questions (0-100)")] = 50,
    hard_percentage: Annotated[int, Form(description="% of hard questions (0-100)")] = 20,

    # --- Paper metadata (all optional) ---
    institution_name: Annotated[str, Form()] = "University",
    course_name: Annotated[str, Form()] = "Course",
    course_code: Annotated[str, Form()] = "CS101",
    semester: Annotated[str, Form()] = "I",
    exam_type: Annotated[str, Form()] = "End Semester Examination",
    duration: Annotated[str, Form()] = "3 Hours",
    exam_date: Annotated[Optional[str], Form(description="Optional exam date")] = None,
) -> GenerateResponse:
    """
    Full pipeline endpoint:
    1. Validate and save uploaded file
    2. Ingest via RAG (chunk + embed)
    3. Run Orchestrator (LangGraph workflow + PDF generation)
    4. Return paths to generated PDFs
    """

    # ------------------------------------------------------------------
    # Validate, read, and save upload
    # ------------------------------------------------------------------
    file_names: list[str] = []
    upload_paths: list[str] = []
    total_size_mb = 0.0
    if files:
        file_names, upload_paths, total_size_mb, _paths = await _save_and_validate_uploads(files)

    selected_file_ids = _json_id_list(google_file_ids, "google_file_ids")
    selected_folder_ids = _json_id_list(google_folder_ids, "google_folder_ids")
    if selected_file_ids or selected_folder_ids:
        if not google_session_id:
            raise HTTPException(status_code=400, detail="Connect Google before selecting Drive or Classroom documents.")
        try:
            imported = download_selection(
                _google_creds(google_session_id), selected_file_ids, selected_folder_ids,
                settings.paths.GOOGLE_IMPORTED_DOCUMENTS_DIR / uuid4().hex,
                settings.api.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not import selected Google documents: {exc}") from exc
        upload_paths.extend(str(path) for path in imported)
        file_names.extend(path.name for path in imported)
        total_size_mb += sum(path.stat().st_size for path in imported) / (1024 * 1024)

    if not upload_paths:
        raise HTTPException(status_code=400, detail="Select at least one manual, Drive, or Classroom document.")

    logger.info(
        f"Received {len(file_names)} file(s) ({total_size_mb:.2f} MB total): "
        f"{', '.join(file_names)}"
    )

    # ------------------------------------------------------------------
    # Build distribution and metadata dicts
    # ------------------------------------------------------------------
    distribution: QuestionDistribution = QuestionDistribution(
        total_marks=total_marks,
        two_mark_questions=two_mark_questions,
        five_mark_questions=five_mark_questions,
        ten_mark_questions=ten_mark_questions,
        fifteen_mark_questions=fifteen_mark_questions,
        easy_percentage=easy_percentage,
        medium_percentage=medium_percentage,
        hard_percentage=hard_percentage,
    )

    paper_metadata: PaperMetadata = PaperMetadata(
        institution_name=institution_name,
        course_name=course_name,
        course_code=course_code,
        semester=semester,
        exam_type=exam_type,
        duration=duration,
        maximum_marks=total_marks,
        date=exam_date,
    )

    # ------------------------------------------------------------------
    # Run Orchestrator (RAG ingest → agents → PDFs)
    # ------------------------------------------------------------------
    if _orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator is not initialised. Service is starting up.",
        )

    result: OrchestratorResult = _orchestrator.run(
        uploaded_file_paths=upload_paths,
        distribution=distribution,
        paper_metadata=paper_metadata,
    )

    # ------------------------------------------------------------------
    # Build response
    # ------------------------------------------------------------------
    if result.success:
        message = (
            f"Question paper and answer key generated successfully "
            f"from {result.rag_chunk_count} RAG chunk(s) in {result.elapsed_seconds:.1f}s."
        )
    else:
        message = (
            f"Generation failed after {result.elapsed_seconds:.1f}s. "
            "See errors for details."
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=GenerateResponse(
                success=result.success,
                message=message,
                final_pdf_path=result.final_pdf_path,
                answer_key_pdf_path=result.answer_key_pdf_path,
                elapsed_seconds=result.elapsed_seconds,
                rag_chunk_count=result.rag_chunk_count,
                errors=result.errors,
                debug=result.debug_info,
                questions=result.final_state.get("validated_questions") if result.final_state else None,
                answer_key=result.final_state.get("answer_key") if result.final_state else None,
            ).model_dump(),
        )

    return GenerateResponse(
        success=result.success,
        message=message,
        final_pdf_path=result.final_pdf_path,
        answer_key_pdf_path=result.answer_key_pdf_path,
        elapsed_seconds=result.elapsed_seconds,
        rag_chunk_count=result.rag_chunk_count,
        errors=result.errors,
        debug=result.debug_info,
        questions=result.final_state.get("validated_questions") if result.final_state else None,
        answer_key=result.final_state.get("answer_key") if result.final_state else None,
    )


@app.post(
    "/generate/pdf",
    response_model=GenerateResponse,
    tags=["Generation"],
    summary="Compile edited questions and answer key into PDFs",
)
async def compile_edited_pdfs(req: PrintPdfRequest) -> GenerateResponse:
    """
    Compile custom edited questions and answer key list into brand new PDFs.
    """
    start_time = time.perf_counter()
    logger.info("Main: Compiling custom edited PDFs...")
    try:
        from app.services.pdf_generator import PDFGenerator
        metadata_dict = req.paper_metadata.model_dump()
        pdf_generator = PDFGenerator()

        # 1. Generate custom question paper PDF
        final_pdf_path = pdf_generator.generate_question_paper(
            validated_questions=req.questions,
            paper_metadata=metadata_dict,
        )

        # 2. Generate custom answer key PDF
        answer_key_pdf_path = pdf_generator.generate_answer_key(
            answer_key=req.answer_key,
            paper_metadata=metadata_dict,
        )

        elapsed = time.perf_counter() - start_time
        return GenerateResponse(
            success=True,
            message=f"PDFs generated successfully in {elapsed:.1f}s.",
            final_pdf_path=final_pdf_path,
            answer_key_pdf_path=answer_key_pdf_path,
            elapsed_seconds=elapsed,
            rag_chunk_count=0,
            errors=[],
            debug={},
            questions=req.questions,
            answer_key=req.answer_key,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.error(f"Main: Custom PDF compilation failed: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=GenerateResponse(
                success=False,
                message=f"Custom PDF generation failed: {exc}",
                final_pdf_path=None,
                answer_key_pdf_path=None,
                elapsed_seconds=elapsed,
                errors=[str(exc)],
            ).model_dump(),
        )


@app.post(
    "/answer-key/update",
    response_model=GenerateResponse,
    tags=["Generation"],
    summary="Regenerate answer-key entries for edited questions",
)
async def update_answer_key(req: UpdateAnswerKeyRequest) -> GenerateResponse:
    """Refresh only the answer-key entries corresponding to edited draft questions."""
    start_time = time.perf_counter()
    modified_ids = {question_id.strip() for question_id in req.modified_question_ids if question_id.strip()}
    questions_by_id = {
        question.get("id"): question
        for question in req.questions
        if isinstance(question.get("id"), str) and question.get("id")
    }

    if not modified_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select at least one edited question before updating the answer key.",
        )

    missing_ids = modified_ids - questions_by_id.keys()
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Edited question IDs are not present in the draft: {', '.join(sorted(missing_ids))}",
        )

    edited_questions = [question for question in req.questions if question.get("id") in modified_ids]
    logger.info("Main: Regenerating answer-key entries for %s edited question(s).", len(edited_questions))

    try:
        from app.agents.answerkey_agent import answerkey_agent_node

        agent_result = answerkey_agent_node({
            "validated_questions": edited_questions,
            "content_context": "",
            "status": "running",
            "errors": [],
        })
        generated_entries = agent_result.get("answer_key", [])
        generated_by_id = {
            entry.get("id"): entry
            for entry in generated_entries
            if isinstance(entry, dict) and entry.get("id") in modified_ids
        }
        unresolved_ids = modified_ids - generated_by_id.keys()
        if unresolved_ids:
            errors = agent_result.get("errors", [])
            detail = (
                "Could not regenerate answer keys for: "
                f"{', '.join(sorted(unresolved_ids))}. "
                + (" ".join(errors) if errors else "")
            )
            raise RuntimeError(detail.strip())

        # The edited draft is the canonical source for question text, marks, and images.
        # Keep all non-edited answer-key entries exactly as the user left them.
        refreshed_entries = {
            question_id: {
                **generated_by_id[question_id],
                "id": question_id,
                "question": questions_by_id[question_id]["question"],
                "marks": questions_by_id[question_id]["marks"],
                "image_path": questions_by_id[question_id].get("image_path"),
            }
            for question_id in modified_ids
        }
        updated_answer_key = [
            refreshed_entries.get(entry.get("id"), entry)
            for entry in req.answer_key
        ]
        existing_ids = {entry.get("id") for entry in req.answer_key}
        updated_answer_key.extend(
            refreshed_entries[question_id]
            for question_id in modified_ids
            if question_id not in existing_ids
        )

        elapsed = time.perf_counter() - start_time
        return GenerateResponse(
            success=True,
            message=f"Answer key updated for {len(modified_ids)} edited question(s).",
            elapsed_seconds=elapsed,
            rag_chunk_count=0,
            errors=[],
            debug={},
            questions=req.questions,
            answer_key=updated_answer_key,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Main: Answer-key update failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Answer-key update failed: {exc}",
        ) from exc


@app.get(
    "/papers",
    response_model=PaperListResponse,
    tags=["Files"],
    summary="List all generated papers and answer keys",
)
async def list_papers() -> PaperListResponse:
    """Return a list of all PDF files in the generated_papers/ directory."""
    output_dir: Path = settings.paths.GENERATED_PAPERS_DIR
    pdf_files = sorted(
        [f.name for f in output_dir.glob("*.pdf")],
        reverse=True,
    )
    return PaperListResponse(total=len(pdf_files), files=pdf_files)


@app.get(
    "/download/{filename}",
    tags=["Files"],
    summary="Download a generated PDF by filename",
)
async def download_paper(filename: str) -> FileResponse:
    """
    Stream a generated PDF file for download.

    Args:
        filename: Name of the PDF file (e.g., question_paper_20240611_143022.pdf)
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    filepath = settings.paths.GENERATED_PAPERS_DIR / filename

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{filename}' not found.",
        )

    return FileResponse(
        path=str(filepath),
        media_type="application/pdf",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api.HOST,
        port=settings.api.PORT,
        reload=settings.api.DEBUG,
        log_level=settings.log.LOG_LEVEL.lower(),
    )
