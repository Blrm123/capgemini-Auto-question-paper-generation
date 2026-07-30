"""
subject_profiles/prompt_builder.py

SubjectPromptBuilder — constructs subject-aware LLM prompt sections from a SubjectProfile.

Design:
    - Single Responsibility: only builds prompt text, never loads profiles.
    - The QuestionGeneratorAgent calls build_system_addendum() and
      build_user_context_section() to inject profile content into its prompts.
    - If a profile has prompt_template_override, the full user prompt is replaced.
"""

from __future__ import annotations

from app.subject_profiles.models import SubjectProfile


class SubjectPromptBuilder:
    """
    Constructs prompt sections from a loaded SubjectProfile.

    All methods are pure functions (no side effects, no I/O).
    """

    def __init__(self, profile: SubjectProfile) -> None:
        self._profile = profile

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_system_addendum(self) -> str:
        """
        Build the subject-specific section that is appended to the system prompt.

        Returns a formatted multi-line string with subject rules.
        Returns empty string if the profile has no subject-specific content.
        """
        p = self._profile
        sections: list[str] = []

        sections.append(
            f"\n=== SUBJECT PROFILE: {p.subject_name.upper()} ===\n"
            f"Domain: {p.description}"
        )

        if p.question_styles:
            sections.append(
                "Preferred question styles (use these formats as much as possible):\n"
                + "\n".join(f"  • {s}" for s in p.question_styles)
            )

        if p.blooms_preferences:
            sections.append(
                "Bloom's Taxonomy emphasis (prioritise these cognitive levels):\n"
                + ", ".join(p.blooms_preferences)
            )

        if p.preferred_action_verbs:
            sections.append(
                "Preferred action verbs for this subject:\n"
                + ", ".join(p.preferred_action_verbs)
            )

        if p.forbidden_patterns:
            sections.append(
                "FORBIDDEN question patterns (NEVER generate these):\n"
                + "\n".join(f"  ✗ {f}" for f in p.forbidden_patterns)
            )

        if p.numerical_required:
            sections.append(
                "MANDATORY: At least one numerical / calculation question MUST be included "
                "per mark band where numericals are applicable to the topic."
            )

        if p.diagram_required:
            sections.append(
                "MANDATORY: At least one diagram-based or figure-referenced question "
                "MUST be included if images are available."
            )

        if p.question_guidelines:
            sections.append(
                "Question generation guidelines:\n"
                + "\n".join(f"  {i + 1}. {g}" for i, g in enumerate(p.question_guidelines))
            )

        if p.subject_specific_instructions:
            sections.append(
                "Additional subject-specific instructions:\n"
                + "\n".join(f"  • {instr}" for instr in p.subject_specific_instructions)
            )

        return "\n\n".join(sections)

    def build_answer_guidelines_addendum(self) -> str:
        """
        Build the answer-key section appended to the answer key system prompt.

        Returns the subject-specific answer requirements as a formatted string.
        """
        p = self._profile
        if not p.answer_guidelines:
            return ""

        lines = [
            f"\n=== SUBJECT-SPECIFIC ANSWER REQUIREMENTS: {p.subject_name.upper()} ===",
        ]
        for i, guideline in enumerate(p.answer_guidelines, 1):
            lines.append(f"  {i}. {guideline}")
        return "\n".join(lines)

    def has_prompt_override(self) -> bool:
        """True if this profile defines a full custom user prompt template."""
        return bool(self._profile.prompt_template_override)

    def get_prompt_override(self) -> str | None:
        """Return the custom user prompt template if defined, else None."""
        return self._profile.prompt_template_override

    @property
    def subject_name(self) -> str:
        return self._profile.subject_name

    @property
    def difficulty_hint(self) -> str:
        """Return the difficulty distribution recommendation as a hint string."""
        d = self._profile.difficulty_distribution
        return f"easy: {d.easy}%, medium: {d.medium}%, hard: {d.hard}%"
