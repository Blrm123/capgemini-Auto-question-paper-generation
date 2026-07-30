"""
subject_profiles/

Subject Profile System for the Agentic Question Paper Generator.

This package provides a data-driven, YAML-based subject configuration system
that allows the QuestionGeneratorAgent to produce subject-appropriate questions
without any subject-specific if/else logic in agent code.

Adding a new subject:
    1. Create a new YAML file in subject_profiles/profiles/<subject_slug>.yaml
    2. Follow the schema defined in models.py (SubjectProfile)
    3. No code changes required — the loader discovers profiles automatically.

Exports:
    SubjectProfile          — Pydantic model for a validated profile
    SubjectProfileLoader    — Loads, validates, and caches YAML profiles
    SubjectPromptBuilder    — Constructs LLM prompt sections from a profile
"""

from app.subject_profiles.models import SubjectProfile
from app.subject_profiles.loader import SubjectProfileLoader
from app.subject_profiles.prompt_builder import SubjectPromptBuilder

__all__ = ["SubjectProfile", "SubjectProfileLoader", "SubjectPromptBuilder"]
