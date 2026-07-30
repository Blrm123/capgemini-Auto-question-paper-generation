"""
subject_profiles/models.py

Pydantic model for Subject Profile validation.

Every YAML profile loaded from subject_profiles/profiles/*.yaml is validated
against this model before use. If validation fails, the system falls back to
generic.yaml automatically.

Schema contract:
    - All list fields default to empty lists (never None).
    - All bool fields have explicit defaults.
    - Optional string fields default to None.
    - The prompt_template_override field allows full custom prompts (advanced use).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class DifficultyDistribution(BaseModel):
    """
    Recommended difficulty split for the subject.

    Note: These are RECOMMENDATIONS fed to the LLM prompt as guidance.
    The actual distribution is still controlled by the user-specified
    QuestionDistribution, which takes precedence.
    """
    easy: int = Field(default=30, ge=0, le=100, description="Percentage of easy questions")
    medium: int = Field(default=50, ge=0, le=100, description="Percentage of medium questions")
    hard: int = Field(default=20, ge=0, le=100, description="Percentage of hard questions")

    @field_validator("hard")
    @classmethod
    def percentages_must_sum_to_100(cls, v: int, info) -> int:
        data = info.data
        easy = data.get("easy", 0)
        medium = data.get("medium", 0)
        total = easy + medium + v
        if total != 100:
            raise ValueError(
                f"DifficultyDistribution must sum to 100, got {total} "
                f"(easy={easy}, medium={medium}, hard={v})"
            )
        return v


class SubjectProfile(BaseModel):
    """
    Complete subject configuration profile, loaded from a YAML file.

    Fields:
        subject_name            Human-readable subject name (e.g. "Physics")
        description             One-line description of the subject domain
        question_styles         Preferred question formats (e.g. numerical, essay)
        blooms_preferences      Preferred Bloom's Taxonomy levels to emphasise
        difficulty_distribution Recommended easy/medium/hard split (%)
        question_guidelines     Specific instructions for question generation
        answer_guidelines       Specific instructions for model answer generation
        preferred_action_verbs  Verbs that produce subject-appropriate questions
        forbidden_patterns      Question patterns that must NEVER appear
        numerical_required      Whether numerical/calculation questions are mandatory
        diagram_required        Whether diagram/figure-based questions are needed
        subject_specific_instructions  Domain-specific rules injected into the prompt
        prompt_template_override       Optional: fully replace the question user prompt
    """

    # --- Identity ---
    subject_name: str = Field(..., description="Human-readable subject name")
    description: str = Field(..., description="One-line subject domain description")

    # --- Question Style ---
    question_styles: List[str] = Field(
        default_factory=list,
        description="Preferred question formats (e.g. 'numerical_problem', 'case_study')"
    )
    blooms_preferences: List[str] = Field(
        default_factory=list,
        description="Bloom's levels to emphasise (Remember/Understand/Apply/Analyze/Evaluate/Create)"
    )
    difficulty_distribution: DifficultyDistribution = Field(
        default_factory=DifficultyDistribution,
        description="Recommended difficulty split"
    )

    # --- Generation Guidelines ---
    question_guidelines: List[str] = Field(
        default_factory=list,
        description="Subject-specific question generation rules"
    )
    answer_guidelines: List[str] = Field(
        default_factory=list,
        description="Subject-specific model answer rules"
    )
    preferred_action_verbs: List[str] = Field(
        default_factory=list,
        description="Action verbs suitable for this subject"
    )
    forbidden_patterns: List[str] = Field(
        default_factory=list,
        description="Question patterns that must not appear"
    )

    # --- Special Requirements ---
    numerical_required: bool = Field(
        default=False,
        description="Whether at least one numerical/calculation question is required"
    )
    diagram_required: bool = Field(
        default=False,
        description="Whether at least one diagram/figure-based question is required"
    )

    # --- Domain Instructions ---
    subject_specific_instructions: List[str] = Field(
        default_factory=list,
        description="Additional domain-specific instructions injected verbatim"
    )

    # --- Advanced Override ---
    prompt_template_override: Optional[str] = Field(
        default=None,
        description="If set, replaces the entire question user prompt template"
    )

    @field_validator("blooms_preferences")
    @classmethod
    def validate_bloom_levels(cls, v: List[str]) -> List[str]:
        valid = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
        for level in v:
            if level not in valid:
                raise ValueError(
                    f"Invalid Bloom's level '{level}'. "
                    f"Must be one of: {', '.join(sorted(valid))}"
                )
        return v

    class Config:
        extra = "forbid"   # Reject unknown keys in YAML — prevents silent misconfiguration
