"""
config.py

Central configuration for the Agentic Question Paper Generator.
All settings are loaded from environment variables (via .env file).
No hardcoded secrets or paths anywhere else in the codebase.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Project Root
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Load environment files
# ---------------------------------------------------------------------------
load_dotenv(BASE_DIR / ".env", override=True)
load_dotenv(BASE_DIR / "env", override=True)


# ---------------------------------------------------------------------------
# Groq LLM Configuration
# ---------------------------------------------------------------------------
class LLMConfig:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    USE_VISION_MODEL: bool = os.getenv("USE_VISION_MODEL", "true").lower() == "true"

    # Comma-separated Groq models to rotate through on rate limits or model errors
    FALLBACK_MODELS: list[str] = [
        model.strip()
        for model in os.getenv(
            "FALLBACK_MODELS",
            "llama-3.3-70b-versatile,llama-3.1-8b-instant",
        ).split(",")
        if model.strip()
    ]

    # Generation settings
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    TOP_P: float = float(os.getenv("TOP_P", "0.9"))
    QUESTION_GENERATION_MAX_COMPLETION_TOKENS: int = int(
        os.getenv("QUESTION_GENERATION_MAX_COMPLETION_TOKENS", "8192")
    )
    QUESTION_BATCH_THRESHOLD: int = int(os.getenv("QUESTION_BATCH_THRESHOLD", "25"))
    QUESTION_BATCH_MAX_RETRIES: int = int(os.getenv("QUESTION_BATCH_MAX_RETRIES", "3"))

    # Retry settings for Groq API calls
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "5"))
    RETRY_DELAY_SECONDS: float = float(os.getenv("RETRY_DELAY_SECONDS", "6.0"))

    # Retries when generated questions do not match the requested blueprint
    BLUEPRINT_MAX_RETRIES: int = int(os.getenv("BLUEPRINT_MAX_RETRIES", "2"))

    @classmethod
    def validate(cls) -> None:
        """Raise if critical LLM config is missing."""
        if not cls.GROQ_API_KEY:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Please add it to your .env file."
            )


# ---------------------------------------------------------------------------
# File System Paths
# ---------------------------------------------------------------------------
class PathConfig:
    BASE_DIR: Path = BASE_DIR
    UPLOADED_DOCUMENTS_DIR: Path = BASE_DIR / "uploaded_documents"
    GENERATED_PAPERS_DIR: Path = BASE_DIR / "generated_papers"
    LOGS_DIR: Path = BASE_DIR / "logs"
    GOOGLE_STATE_DIR: Path = BASE_DIR / "google_state"
    GOOGLE_IMPORTED_DOCUMENTS_DIR: Path = BASE_DIR / "google_imported"

    @classmethod
    def ensure_directories(cls) -> None:
        """Create all required directories if they don't exist."""
        for directory in [
            cls.UPLOADED_DOCUMENTS_DIR,
            cls.GENERATED_PAPERS_DIR,
            cls.LOGS_DIR,
            cls.GOOGLE_STATE_DIR,
            cls.GOOGLE_IMPORTED_DOCUMENTS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
class LogConfig:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = PathConfig.LOGS_DIR / "application.log"
    LOG_FORMAT: str = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    # Max log file size before rotation (10 MB)
    MAX_BYTES: int = 10 * 1024 * 1024
    BACKUP_COUNT: int = 5


# ---------------------------------------------------------------------------
# FastAPI Configuration
# ---------------------------------------------------------------------------
class APIConfig:
    HOST: str = os.getenv("API_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    TITLE: str = "Agentic AI Question Paper Generator"
    DESCRIPTION: str = (
        "Multi-Agent AI system that generates university question papers "
        "from uploaded syllabus documents using LangGraph and Groq LLM."
    )
    VERSION: str = "1.0.0"

    # File upload limits (RAG accepts larger syllabus PDFs than the old 10 MB cap)
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "txt", "docx", "xlsx"]

    # Comma-separated browser origins allowed to call the API (React dev server, etc.)
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]


# ---------------------------------------------------------------------------
# PDF Generation Configuration
# ---------------------------------------------------------------------------
class PDFConfig:
    # Paper size: A4 (points: 595 x 842)
    PAGE_WIDTH: float = 595.0
    PAGE_HEIGHT: float = 842.0

    # Margins in points (1 inch = 72 points)
    MARGIN_LEFT: float = 50.4   # 0.70 inch
    MARGIN_RIGHT: float = 39.6  # 0.55 inch
    MARGIN_TOP: float = 43.2    # 0.60 inch
    MARGIN_BOTTOM: float = 43.2 # 0.60 inch

    # Fonts
    FONT_HEADER: str = "Helvetica-Bold"
    FONT_BODY: str = "Helvetica"
    FONT_SIZE_TITLE: int = 14
    FONT_SIZE_HEADER: int = 11
    FONT_SIZE_BODY: int = 10
    FONT_SIZE_FOOTER: int = 8

    # Footer text
    FOOTER_TEXT: str = "Generated by Agentic AI Question Paper Generator"
    DEFAULT_INSTRUCTIONS: tuple[str, ...] = (
        "Answer all questions.",
        "Marks are indicated against each question.",
    )


# ---------------------------------------------------------------------------
# Google Integration Configuration
# ---------------------------------------------------------------------------
class GoogleConfig:
    CLIENT_SECRET_FILE: Path = Path(os.getenv("GOOGLE_CLIENT_SECRET_FILE", str(BASE_DIR / "credentials" / "client_secret.json")))
    REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/google/oauth/callback")
    FRONTEND_REDIRECT_URI: str = os.getenv("GOOGLE_FRONTEND_REDIRECT_URI", "http://localhost:8080/dashboard")


# ---------------------------------------------------------------------------
# Aggregated Settings (single import point for rest of codebase)
# ---------------------------------------------------------------------------
class Settings:
    llm = LLMConfig
    paths = PathConfig
    log = LogConfig
    api = APIConfig
    pdf = PDFConfig
    google = GoogleConfig

    @classmethod
    def initialize(cls) -> None:
        """
        Run all startup checks and directory creation.
        Call once at application startup in main.py.
        """
        cls.paths.ensure_directories()
        cls.llm.validate()


# Singleton-style export
settings = Settings()
