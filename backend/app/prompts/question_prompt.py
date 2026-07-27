"""
prompts/question_prompt.py

Prompt templates for the Question Generator Agent.
"""

QUESTION_SYSTEM_PROMPT = """You are an expert university examination paper setter.

Your response must be a single valid JSON array and nothing else.

Non-negotiable output rules:
- Output only JSON.
- Do not output markdown.
- Do not output code fences.
- Do not output explanations.
- Do not output comments.
- Do not output LaTeX.
- Do not use backslash-based math commands.
- Replace LaTeX with plain Unicode or ASCII text.
- Stop immediately after the final JSON ] character.
- Do not continue generating after the last required question.
- Do not generate more questions than requested.
- Do not repeat the same question with only changed numbers.

Question rules:
- Use exactly these fields for every object:
  id, unit, topic, question, marks, difficulty, question_type, image_path
- difficulty must be exactly one of: easy, medium, hard
- question_type must be exactly one of:
  short for 2 marks
  brief for 5 marks
  long for 10 marks
  essay for 15 marks
- IDs must be sequential: Q001, Q002, Q003, ...
- Base each question strictly on the supplied syllabus and source material.
- Questions must be distinct in concept, not just different numbers.
- Mathematical expressions must be plain text.
- Use Unicode forms such as ×, ÷, ≤, ≥, α when needed.
- Matrix notation must be plain text such as [[1,2],[3,4]].
- If image_path is null, do not refer to a figure.
- If image_path is not null, the question text must refer generically to the figure, diagram, graph, or circuit shown.
- Never mention an image ID inside the question text.
- Never write phrases like "Refer to image xyz123."

Examples:
- Incorrect: \\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}
- Correct: [[1,2],[3,4]]
- Incorrect: 2 \\times 3
- Correct: 2×3
"""


QUESTION_USER_PROMPT_TEMPLATE = """Generate exam questions from the syllabus and source material below.

=== SYLLABUS TOPICS ===
{syllabus_topics_text}

=== RETRIEVED SOURCE MATERIAL ===
{content_context}

=== AVAILABLE IMAGE IDS ===
{available_image_ids}

=== REQUIRED BLUEPRINT ===
Total Marks: {total_marks}
Total Questions: {total_questions}
2-mark questions: {two_mark_count}
5-mark questions: {five_mark_count}
10-mark questions: {ten_mark_count}
15-mark questions: {fifteen_mark_count}

Difficulty distribution:
easy: {easy_pct}%
medium: {medium_pct}%
hard: {hard_pct}%

Generation contract:
- Generate exactly {total_questions} questions.
- Generate exactly {two_mark_count} questions worth 2 marks.
- Generate exactly {five_mark_count} questions worth 5 marks.
- Generate exactly {ten_mark_count} questions worth 10 marks.
- Generate exactly {fifteen_mark_count} questions worth 15 marks.
- Stop immediately after the final required question.
- Never generate extra questions.
- Never wrap the response in markdown or code fences.
- Never output explanatory text before or after the JSON array.
- Never use LaTeX.
- Never use markdown tables.
- If an image is used, store only the image ID in image_path and refer to it only as "the figure shown", "the diagram shown", "the graph shown", or similar generic wording.
- If AVAILABLE IMAGE IDS is (none), image_path must be null for every question.
"""


QUESTION_CORRECTION_ADDENDUM_TEMPLATE = """
=== VALIDATION ERRORS ===
{issues}

Return only a corrected complete JSON array.
Do not explain the fixes.
Do not add new commentary.
Fix only the listed validation errors while preserving valid questions where possible.
The corrected array must still satisfy exactly:
Total Marks: {total_marks}
Total Questions: {total_questions}
2-mark questions: {two_mark_count}
5-mark questions: {five_mark_count}
10-mark questions: {ten_mark_count}
15-mark questions: {fifteen_mark_count}
"""


def build_question_correction_addendum(
    issues: list[str],
    total_marks: int,
    total_questions: int,
    two_mark_count: int,
    five_mark_count: int,
    ten_mark_count: int,
    fifteen_mark_count: int,
) -> str:
    """Build a focused correction block for retry attempts."""
    issues_text = "\n".join(f"- {issue}" for issue in issues)
    return QUESTION_CORRECTION_ADDENDUM_TEMPLATE.format(
        issues=issues_text,
        total_marks=total_marks,
        total_questions=total_questions,
        two_mark_count=two_mark_count,
        five_mark_count=five_mark_count,
        ten_mark_count=ten_mark_count,
        fifteen_mark_count=fifteen_mark_count,
    )


def build_question_user_prompt(
    syllabus_topics: list,
    content_context: str,
    total_marks: int,
    total_questions: int,
    two_mark_count: int,
    five_mark_count: int,
    ten_mark_count: int,
    fifteen_mark_count: int,
    easy_pct: int,
    medium_pct: int,
    hard_pct: int,
    available_image_ids: str = "(none)",
) -> str:
    """Build the user prompt for question generation."""
    topics_lines = []
    for unit in syllabus_topics:
        topics_lines.append(f"Unit {unit['unit_number']}: {unit['unit_name']}")
        for topic in unit["topics"]:
            topics_lines.append(f"  - {topic}")

    return QUESTION_USER_PROMPT_TEMPLATE.format(
        syllabus_topics_text="\n".join(topics_lines),
        content_context=content_context.strip() or "(No source material chunks available)",
        available_image_ids=available_image_ids or "(none)",
        total_marks=total_marks,
        total_questions=total_questions,
        two_mark_count=two_mark_count,
        five_mark_count=five_mark_count,
        ten_mark_count=ten_mark_count,
        fifteen_mark_count=fifteen_mark_count,
        easy_pct=easy_pct,
        medium_pct=medium_pct,
        hard_pct=hard_pct,
    )
