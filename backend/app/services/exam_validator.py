"""Deterministic, non-LLM acceptance checks for printable examinations.

Checks are split into two tiers:
  - hard_errors  : arithmetic / structural invariants that MUST hold
                   (marks totals, question counts, unique IDs, empty questions)
  - soft_warnings: quality-of-paper checks that SHOULD hold but cannot be
                   guaranteed by the LLM (difficulty distribution, unit coverage,
                   Bloom level variety, near-duplicates, topic evidence)

Only hard_errors block PDF generation.  Soft warnings are logged and returned
in the report for human review.
"""

from collections import Counter
import math
import re
from typing import Any

from app.services.blueprint_utils import (
    blueprint_mismatch_messages,
    expected_total_questions,
)


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "write",
    "explain", "describe", "discuss", "calculate", "using", "given", "following",
}


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]{3,}", text.lower())
        if token not in _STOPWORDS
    }


def _expected_difficulties(total_questions: int, distribution: dict[str, Any]) -> dict[str, int]:
    """Use largest-remainder allocation so percentages are deterministic."""
    raw = {
        level: total_questions * int(distribution[f"{level}_percentage"]) / 100
        for level in ("easy", "medium", "hard")
    }
    allocated = {level: math.floor(value) for level, value in raw.items()}
    remaining = total_questions - sum(allocated.values())
    for level, _ in sorted(raw.items(), key=lambda item: (item[1] % 1, item[0]), reverse=True)[:remaining]:
        allocated[level] += 1
    return allocated


def validate_exam_blueprint(
    questions: list[dict[str, Any]],
    distribution: dict[str, Any],
    syllabus_topics: list[dict[str, Any]],
    content_context: str,
) -> dict[str, Any]:
    """Return an auditable pass/fail report without trusting an LLM verdict.

    Only ``hard_errors`` cause ``passed`` to be False and block PDF generation.
    ``warnings`` are quality issues logged for review but never blocking.
    """
    hard_errors: list[str] = []
    warnings: list[str] = []
    expected_count = expected_total_questions(distribution)

    # ── HARD: blueprint counts and total marks ────────────────────────────
    hard_errors.extend(blueprint_mismatch_messages(questions, distribution))

    # ── HARD: IDs non-empty and unique ────────────────────────────────────
    ids = [str(question.get("id", "")).strip() for question in questions]
    if not all(ids):
        hard_errors.append("Every question must have a non-empty ID.")
    if len(ids) != len(set(ids)):
        hard_errors.append("Question IDs must be unique.")

    # ── HARD: invalid marks values ────────────────────────────────────────
    marks = Counter()
    for question in questions:
        try:
            marks[int(question.get("marks"))] += 1
        except (TypeError, ValueError):
            hard_errors.append(f"Question {question.get('id', '?')} has invalid marks.")

    # ── HARD: empty questions ─────────────────────────────────────────────
    for question in questions:
        q_tokens = _tokens(str(question.get("question", "")))
        if not q_tokens:
            hard_errors.append(f"Question {question.get('id', '?')} is empty.")

    # ── SOFT: difficulty distribution ─────────────────────────────────────
    expected_difficulty = _expected_difficulties(expected_count, distribution)
    actual_difficulty = Counter(str(question.get("difficulty", "")).lower() for question in questions)
    for level, expected in expected_difficulty.items():
        if actual_difficulty[level] != expected:
            warnings.append(f"Expected {expected} {level} question(s); found {actual_difficulty[level]}.")

    # ── SOFT: unit coverage (fuzzy word-overlap matching) ─────────────────
    required_units = [str(unit.get("unit_name", "")).strip().casefold() for unit in syllabus_topics if unit.get("unit_name")]
    present_units = [str(question.get("unit", "")).strip().casefold() for question in questions]

    def _unit_covered(required: str, present_set: list[str]) -> bool:
        required_words = set(required.split())
        for p in present_set:
            p_words = set(p.split())
            if required_words & p_words:
                return True
        return False

    missing_units = sorted(u for u in required_units if not _unit_covered(u, present_units))
    if missing_units:
        warnings.append("Missing syllabus unit coverage: " + ", ".join(missing_units) + ".")

    # ── SOFT: Bloom level variety ─────────────────────────────────────────
    bloom_levels = {str(question.get("bloom_level", "")).strip() for question in questions}
    minimum_bloom_levels = min(4, expected_count)
    if len(bloom_levels - {""}) < minimum_bloom_levels:
        warnings.append(f"Expected at least {minimum_bloom_levels} Bloom levels; found {len(bloom_levels - {''})}.")

    # ── SOFT: near-duplicate detection ────────────────────────────────────
    for index, left in enumerate(questions):
        left_tokens = _tokens(str(left.get("question", "")))
        if not left_tokens:
            continue  # already caught above as hard error
        for right in questions[index + 1:]:
            right_tokens = _tokens(str(right.get("question", "")))
            union = left_tokens | right_tokens
            if union and len(left_tokens & right_tokens) / len(union) >= 0.82:
                warnings.append(f"Questions {left.get('id', '?')} and {right.get('id', '?')} are near-duplicates.")

    # ── SOFT: topic evidence in retrieved context ─────────────────────────
    context_tokens = _tokens(content_context)
    evidence: dict[str, dict[str, Any]] = {}
    for question in questions:
        q_id = str(question.get("id", "?"))
        topic_tokens = _tokens(str(question.get("topic", "")))
        matched = sorted(topic_tokens & context_tokens)
        evidence[q_id] = {"topic_terms_found": matched, "grounded": bool(matched)}
        if topic_tokens and not matched:
            warnings.append(f"Question {q_id} has no topic-term evidence in retrieved context.")

    return {
        "passed": not hard_errors,
        "errors": hard_errors,
        "warnings": warnings,
        "expected_question_count": expected_count,
        "actual_question_count": len(questions),
        "expected_difficulty": expected_difficulty,
        "actual_difficulty": dict(actual_difficulty),
        "marks": dict(marks),
        "evidence": evidence,
    }
