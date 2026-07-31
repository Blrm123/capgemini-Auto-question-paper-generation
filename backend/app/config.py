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
# Google Gemini Configuration (Primary LLM Provider)
# ---------------------------------------------------------------------------
class GeminiConfig:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")

    # Per-agent model configuration (Editable via .env)
    MODEL_PDF_PARSER: str = os.getenv("MODEL_PDF_PARSER", "gemini-3.5-flash-lite")
    MODEL_SYLLABUS_AGENT: str = os.getenv("MODEL_SYLLABUS_AGENT", "gemini-3.5-flash-lite")
    MODEL_QUESTION_GENERATOR: str = os.getenv("MODEL_QUESTION_GENERATOR", "gemini-3.5-flash-lite")
    MODEL_BLOOM_AGENT: str = os.getenv("MODEL_BLOOM_AGENT", "gemini-3.1-flash-lite")
    MODEL_VALIDATION_AGENT: str = os.getenv("MODEL_VALIDATION_AGENT", "gemini-3.1-flash-lite")
    MODEL_DIFFICULTY_CLASSIFIER: str = os.getenv("MODEL_DIFFICULTY_CLASSIFIER", "gemini-3.1-flash-lite")
    MODEL_DUPLICATE_DETECTOR: str = os.getenv("MODEL_DUPLICATE_DETECTOR", "gemini-3.1-flash-lite")
    MODEL_ANSWER_KEY_AGENT: str = os.getenv("MODEL_ANSWER_KEY_AGENT", "gemini-3.5-flash-lite")

    @classmethod
    def get_model_for_agent(cls, agent_name: str) -> str:
        """Resolve model name configured in .env for a given agent/task."""
        mapping = {
            "PDFParser": cls.MODEL_PDF_PARSER,
            "ImageDescriptorAgent": cls.MODEL_PDF_PARSER,
            "SyllabusAgent": cls.MODEL_SYLLABUS_AGENT,
            "QuestionGeneratorAgent": cls.MODEL_QUESTION_GENERATOR,
            "BloomAgent": cls.MODEL_BLOOM_AGENT,
            "ValidationAgent": cls.MODEL_VALIDATION_AGENT,
            "DifficultyClassifier": cls.MODEL_DIFFICULTY_CLASSIFIER,
            "DuplicateDetector": cls.MODEL_DUPLICATE_DETECTOR,
            "AnswerKeyAgent": cls.MODEL_ANSWER_KEY_AGENT,
        }
        val = mapping.get(agent_name)
        if val and val.strip():
            return val.strip()
        return cls.GEMINI_MODEL_NAME

    @classmethod
    def is_available(cls) -> bool:
        """True if a Gemini API key is configured."""
        return bool(cls.GEMINI_API_KEY.strip())

    @classmethod
    def validate(cls) -> None:
        """Raise if Gemini is selected as provider but key is missing."""
        if not cls.GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey "
                "and add it to your .env file."
            )


# ---------------------------------------------------------------------------
# Groq LLM Configuration (Fallback Provider)
# ---------------------------------------------------------------------------
class LLMConfig:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    USE_VISION_MODEL: bool = os.getenv("USE_VISION_MODEL", "true").lower() == "true"

    # FALLBACK_MODELS: only add models here if you want context-aware fallback.
    # WARNING: switching to a smaller model (e.g. 8b) during generation breaks
    # context quality. Leave empty to retry on the same model with delay instead.
    FALLBACK_MODELS: list[str] = [
        model.strip()
        for model in os.getenv(
            "FALLBACK_MODELS",
            "llama-3.3-70b-versatile",
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
        """Raise if Groq is the selected provider but key is missing."""
        if not cls.GROQ_API_KEY:
            raise EnvironmentError(
                "GROQ_API_KEY is not set and GEMINI_API_KEY is also not set. "
                "Please add at least one LLM API key to your .env file. "
                "Recommended: Set GEMINI_API_KEY (free at https://aistudio.google.com/app/apikey)."
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
    ANALYTICS_FILE: Path = LOGS_DIR / "analytics.json"

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
    TITLE: str = "QUBIT"
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
            "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
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
    FOOTER_TEXT: str = "Generated by QUBIT"
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
    FRONTEND_REDIRECT_URI: str = os.getenv("GOOGLE_FRONTEND_REDIRECT_URI", "http://localhost:3000/dashboard")


# ---------------------------------------------------------------------------
# Aggregated Settings (single import point for rest of codebase)
# ---------------------------------------------------------------------------
class Settings:
    llm = LLMConfig
    gemini = GeminiConfig
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
        # Validate whichever provider is active
        if cls.gemini.is_available():
            cls.gemini.validate()
        else:
            cls.llm.validate()

    @classmethod
    def active_provider(cls) -> str:
        """Returns 'gemini' if Gemini API key is set, else 'groq'."""
        return "gemini" if cls.gemini.is_available() else "groq"


# Singleton-style export
settings = Settings()
