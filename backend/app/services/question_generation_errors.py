"""Custom exceptions for production-grade question generation."""


class QuestionGenerationError(Exception):
    """Base exception for question generation failures."""


class JSONRepairError(QuestionGenerationError):
    """Raised when malformed JSON cannot be repaired."""


class BlueprintMismatchError(QuestionGenerationError):
    """Raised when output does not match the requested blueprint."""


class SchemaValidationError(QuestionGenerationError):
    """Raised when generated data fails schema or business validation."""


class OutputTooLargeError(QuestionGenerationError):
    """Raised when a generation request is too large for a single batch."""
