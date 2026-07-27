from app.agents.question_generator_agent import QuestionGeneratorAgent


class _FakeRegistry:
    def __init__(self, valid_ids: set[str] | None = None) -> None:
        self.valid_ids = valid_ids or set()

    def is_valid_image_id(self, image_id: str) -> bool:
        return image_id in self.valid_ids

    def get_relative_path(self, image_id: str) -> str:
        return f"uploaded_documents/{image_id}.png"


def _distribution() -> dict:
    return {
        "total_marks": 9,
        "two_mark_questions": 2,
        "five_mark_questions": 1,
        "ten_mark_questions": 0,
        "fifteen_mark_questions": 0,
        "easy_percentage": 30,
        "medium_percentage": 50,
        "hard_percentage": 20,
    }


def _question(q_id: str, marks: int, text: str, **extra) -> dict:
    question_type = {2: "short", 5: "brief", 10: "long", 15: "essay"}[marks]
    question = {
        "id": q_id,
        "unit": "Unit 1",
        "topic": "Topic A",
        "question": text,
        "marks": marks,
        "difficulty": "medium",
        "question_type": question_type,
        "image_path": None,
    }
    question.update(extra)
    return question


def test_validate_output_detects_duplicate_questions() -> None:
    agent = QuestionGeneratorAgent()
    questions = [
        _question("Q001", 2, "Define inertia."),
        _question("Q002", 2, "Define inertia."),
        _question("Q003", 5, "Explain Newton's first law."),
    ]

    issues = agent._validate_output(
        questions=questions,
        distribution=_distribution(),
        registry=None,
        allowed_image_ids=set(),
    )

    assert any("Duplicate questions detected" in issue for issue in issues)


def test_validate_output_detects_incorrect_counts() -> None:
    agent = QuestionGeneratorAgent()
    questions = [
        _question("Q001", 2, "Define inertia."),
        _question("Q002", 5, "Explain Newton's first law."),
    ]

    issues = agent._validate_output(
        questions=questions,
        distribution=_distribution(),
        registry=None,
        allowed_image_ids=set(),
    )

    assert any("Expected 3 questions, found 2." in issue for issue in issues)


def test_validate_output_detects_malformed_ids() -> None:
    agent = QuestionGeneratorAgent()
    questions = [
        _question("Q010", 2, "Define inertia."),
        _question("Q002", 2, "Define momentum."),
        _question("Q003", 5, "Explain Newton's first law."),
    ]

    issues = agent._validate_output(
        questions=questions,
        distribution=_distribution(),
        registry=None,
        allowed_image_ids=set(),
    )

    assert any("IDs must be sequential" in issue for issue in issues)


def test_validate_output_detects_invalid_image_path() -> None:
    agent = QuestionGeneratorAgent()
    questions = [
        _question(
            "Q001",
            2,
            "Refer to the figure shown. Define inertia.",
            image_path="uploaded_documents/missing.png",
        ),
        _question("Q002", 2, "Define momentum."),
        _question("Q003", 5, "Explain Newton's first law."),
    ]

    issues = agent._validate_output(
        questions=questions,
        distribution=_distribution(),
        registry=_FakeRegistry({"img1"}),
        allowed_image_ids={"img1"},
    )

    assert any("invalid image_path" in issue for issue in issues)


def test_validate_output_detects_markdown_output() -> None:
    agent = QuestionGeneratorAgent()
    questions = [
        _question("Q001", 2, "```Define inertia.```"),
        _question("Q002", 2, "Define momentum."),
        _question("Q003", 5, "Explain Newton's first law."),
    ]

    issues = agent._validate_output(
        questions=questions,
        distribution=_distribution(),
        registry=None,
        allowed_image_ids=set(),
    )

    assert any("markdown formatting" in issue for issue in issues)


def test_validate_output_detects_question_text_image_id_reference() -> None:
    agent = QuestionGeneratorAgent()
    questions = [
        _question(
            "Q001",
            2,
            "Refer to image img1 and define inertia.",
            image_path="uploaded_documents/img1.png",
        ),
        _question("Q002", 2, "Define momentum."),
        _question("Q003", 5, "Explain Newton's first law."),
    ]

    issues = agent._validate_output(
        questions=questions,
        distribution=_distribution(),
        registry=None,
        allowed_image_ids={"img1"},
    )

    assert any("must not mention image IDs" in issue for issue in issues)
