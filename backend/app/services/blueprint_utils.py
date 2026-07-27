"""Shared blueprint helpers for question count and marks distribution.

All expected counts are derived from ``QuestionDistribution`` — nothing is
hardcoded to a specific exam size or mark total.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Mark value ↔ distribution field names (matches QuestionDistribution schema)
MARK_BANDS: tuple[tuple[int, str], ...] = (
    (2, "two_mark_questions"),
    (5, "five_mark_questions"),
    (10, "ten_mark_questions"),
    (15, "fifteen_mark_questions"),
)

VALID_MARK_VALUES: frozenset[int] = frozenset(mark for mark, _ in MARK_BANDS)

MARKS_TO_QUESTION_TYPE: dict[int, str] = {
    mark: question_type
    for mark, question_type in ((2, "short"), (5, "brief"), (10, "long"), (15, "essay"))
}


def expected_marks_counts(distribution: dict[str, Any]) -> dict[int, int]:
    """Return expected question count per mark value from the distribution."""
    return {mark: int(distribution[field]) for mark, field in MARK_BANDS}


def expected_total_questions(distribution: dict[str, Any]) -> int:
    """Total number of questions implied by the distribution."""
    return sum(expected_marks_counts(distribution).values())


def expected_total_marks(distribution: dict[str, Any]) -> int:
    """Total marks implied by per-band counts (ignores ``total_marks`` field)."""
    return sum(mark * count for mark, count in expected_marks_counts(distribution).items())


def count_questions_by_marks(questions: list[dict[str, Any]]) -> Counter:
    """Count questions grouped by mark value; invalid marks are skipped."""
    counts: Counter = Counter()
    for question in questions:
        try:
            mark = int(question.get("marks"))
        except (TypeError, ValueError):
            continue
        if mark in VALID_MARK_VALUES:
            counts[mark] += 1
    return counts


def blueprint_mismatch_messages(
    questions: list[dict[str, Any]],
    distribution: dict[str, Any],
) -> list[str]:
    """Return human-readable errors when questions do not match the blueprint."""
    messages: list[str] = []
    expected_counts = expected_marks_counts(distribution)
    expected_total = expected_total_questions(distribution)
    actual_counts = count_questions_by_marks(questions)

    if len(questions) != expected_total:
        messages.append(
            f"Expected {expected_total} questions, found {len(questions)}."
        )

    for mark, field in MARK_BANDS:
        expected = expected_counts[mark]
        actual = actual_counts.get(mark, 0)
        if actual != expected:
            messages.append(
                f"Expected {expected} question(s) worth {mark} marks; found {actual}."
            )

    actual_total = sum(mark * count for mark, count in actual_counts.items())
    target_total = int(distribution["total_marks"])
    if actual_total != target_total:
        messages.append(
            f"Question marks total {actual_total}, expected {target_total}."
        )

    return messages


def _question_keep_score(question: dict[str, Any], band: list[dict[str, Any]]) -> int:
    """Higher score means the question should be kept when trimming excess."""
    score = 0
    if question.get("image_path"):
        score += 100

    unit = str(question.get("unit", "")).casefold()
    topic = str(question.get("topic", "")).casefold()
    duplicates = sum(
        1
        for other in band
        if str(other.get("unit", "")).casefold() == unit
        and str(other.get("topic", "")).casefold() == topic
    )
    score += max(0, 60 - duplicates * 15)
    return score


def _select_questions_for_band(
    band: list[dict[str, Any]],
    keep_count: int,
) -> list[dict[str, Any]]:
    """Keep the best ``keep_count`` questions from a mark band."""
    if keep_count <= 0:
        return []
    if len(band) <= keep_count:
        return list(band)
    ranked = sorted(
        band,
        key=lambda question: (_question_keep_score(question, band), question.get("id", "")),
        reverse=True,
    )
    return ranked[:keep_count]


def reconcile_questions_to_blueprint(
    questions: list[dict[str, Any]],
    distribution: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Trim excess questions per mark band to match the distribution.

    Questions with mark values outside the blueprint are dropped. Deficits are
    not filled — callers must detect those via ``blueprint_mismatch_messages``.
    """
    expected_counts = expected_marks_counts(distribution)
    actions: list[str] = []
    by_mark: dict[int, list[dict[str, Any]]] = {mark: [] for mark in expected_counts}

    for question in questions:
        try:
            mark = int(question.get("marks"))
        except (TypeError, ValueError):
            actions.append(
                f"Dropped question {question.get('id', '?')} with invalid marks during reconciliation."
            )
            continue
        if mark not in by_mark:
            actions.append(
                f"Dropped question {question.get('id', '?')} with unsupported marks {mark}."
            )
            continue
        by_mark[mark].append(question)

    reconciled: list[dict[str, Any]] = []
    for mark in sorted(expected_counts):
        needed = expected_counts[mark]
        band = by_mark[mark]
        if len(band) > needed:
            kept = _select_questions_for_band(band, needed)
            kept_ids = {item.get("id") for item in kept}
            for item in band:
                if item.get("id") not in kept_ids:
                    actions.append(
                        f"Dropped excess {mark}-mark question {item.get('id', '?')} "
                        "during blueprint reconciliation."
                    )
            reconciled.extend(kept)
        else:
            reconciled.extend(band)

    return renumber_question_ids(reconciled), actions


def renumber_question_ids(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign sequential IDs (Q001, Q002, …) in mark-band order."""
    ordered: list[dict[str, Any]] = []
    mark_order = [mark for mark, _ in MARK_BANDS]
    for mark in mark_order:
        band = [question for question in questions if int(question.get("marks", 0)) == mark]
        band.sort(key=lambda question: str(question.get("id", "")))
        ordered.extend(band)

    renumbered: list[dict[str, Any]] = []
    for index, question in enumerate(ordered, start=1):
        updated = dict(question)
        updated["id"] = f"Q{index:03d}"
        renumbered.append(updated)
    return renumbered
