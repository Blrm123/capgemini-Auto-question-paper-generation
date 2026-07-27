"""Unit tests for blueprint distribution helpers."""

import json

import pytest

from app.services.blueprint_utils import (
    blueprint_mismatch_messages,
    expected_total_questions,
    reconcile_questions_to_blueprint,
    renumber_question_ids,
)
from app.services.llm_service import LLMService


def _sample_distribution() -> dict:
    return {
        "total_marks": 100,
        "two_mark_questions": 5,
        "five_mark_questions": 6,
        "ten_mark_questions": 3,
        "fifteen_mark_questions": 2,
        "easy_percentage": 30,
        "medium_percentage": 50,
        "hard_percentage": 20,
    }


def _question(q_id: str, marks: int, **extra) -> dict:
    base = {
        "id": q_id,
        "unit": "Unit 1",
        "topic": f"Topic {q_id}",
        "question": f"Question text for {q_id}",
        "marks": marks,
        "difficulty": "medium",
        "question_type": "brief",
        "image_path": None,
    }
    base.update(extra)
    return base


def test_expected_total_questions_from_distribution():
    distribution = _sample_distribution()
    assert expected_total_questions(distribution) == 16


def test_blueprint_mismatch_detects_extra_five_mark_questions():
    distribution = _sample_distribution()
    questions = (
        [_question(f"Q{i:03d}", 2) for i in range(1, 6)]
        + [_question(f"Q{i:03d}", 5) for i in range(6, 13)]
        + [_question(f"Q{i:03d}", 10) for i in range(13, 16)]
        + [_question(f"Q{i:03d}", 15) for i in range(16, 18)]
    )

    issues = blueprint_mismatch_messages(questions, distribution)
    assert any("Expected 16 questions, found 17." in issue for issue in issues)
    assert any("Expected 6 question(s) worth 5 marks; found 7." in issue for issue in issues)
    assert any("Question marks total 105, expected 100." in issue for issue in issues)


def test_reconcile_trims_excess_and_renumbers():
    distribution = _sample_distribution()
    questions = (
        [_question(f"Q{i:03d}", 2) for i in range(1, 6)]
        + [_question(f"Q{i:03d}", 5) for i in range(6, 13)]
        + [_question(f"Q{i:03d}", 10) for i in range(13, 16)]
        + [_question(f"Q{i:03d}", 15) for i in range(16, 18)]
    )

    reconciled, actions = reconcile_questions_to_blueprint(questions, distribution)
    assert len(reconciled) == 16
    assert blueprint_mismatch_messages(reconciled, distribution) == []
    assert [question["id"] for question in reconciled] == [f"Q{i:03d}" for i in range(1, 17)]
    assert any("Dropped excess 5-mark question" in action for action in actions)


def test_reconcile_prefers_questions_with_images():
    distribution = {
        "total_marks": 10,
        "two_mark_questions": 5,
        "five_mark_questions": 0,
        "ten_mark_questions": 0,
        "fifteen_mark_questions": 0,
        "easy_percentage": 30,
        "medium_percentage": 50,
        "hard_percentage": 20,
    }
    questions = [
        _question("Q001", 2),
        _question("Q002", 2),
        _question("Q003", 2),
        _question("Q004", 2),
        _question("Q005", 2),
        _question("Q006", 2, image_path="diagram.png"),
    ]

    reconciled, _ = reconcile_questions_to_blueprint(questions, distribution)
    assert len(reconciled) == 5
    assert any(question.get("image_path") == "diagram.png" for question in reconciled)


def test_renumber_question_ids_orders_by_mark_band():
    questions = [
        _question("Q010", 10),
        _question("Q002", 2),
        _question("Q005", 5),
    ]
    renumbered = renumber_question_ids(questions)
    assert [question["marks"] for question in renumbered] == [2, 5, 10]
    assert [question["id"] for question in renumbered] == ["Q001", "Q002", "Q003"]


def test_llm_service_repairs_invalid_star_escape():
    raw = r'[{"model_answer": "E = E0 - (RT/nF) \* ln(Q)"}]'
    repaired = LLMService.repair_json_invalid_escapes(raw)
    parsed = json.loads(repaired)
    assert "* ln(Q)" in parsed[0]["model_answer"]
