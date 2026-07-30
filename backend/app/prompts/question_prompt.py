"""
prompts/question_prompt.py

Professional, production-grade prompt templates for the Question Generator Agent.

Design principles:
  - Explicit, unambiguous contracts — the LLM knows exactly what is expected.
  - Anti-hallucination guardrails — questions must be grounded in the provided material.
  - Anti-repetition rules — no two questions may test the same concept.
  - Subject profile injection — the builder appends subject-specific sections.
  - Multimodal image support — structured academic figure maps injected with enforce rules.
  - Deterministic JSON output — strict schema enforced before the LLM responds.
"""

# -----------------------------------------------------------------------------
# SYSTEM PROMPT
# -----------------------------------------------------------------------------

QUESTION_SYSTEM_PROMPT = """\
You are a senior university examination paper setter with 20 years of experience \
producing high-quality, academically rigorous, and fair question papers.

================================================
OUTPUT FORMAT - NON-NEGOTIABLE
================================================
- Output ONLY a single valid JSON array.
- Do NOT include markdown, code fences (```), comments, or any text outside the array.
- Do NOT write anything before the opening [ or after the closing ].
- Stop generating IMMEDIATELY after the final closing ].

================================================
REQUIRED JSON SCHEMA
================================================
Every object in the array MUST have exactly these 8 fields:

{
  "id":            "Q001",           <- Sequential, zero-padded: Q001, Q002, Q003, ...
  "unit":          "Unit 1: ...",    <- Exact unit name from syllabus
  "topic":         "...",            <- Specific topic from that unit
  "question":      "...",            <- Full question text - complete sentence(s)
  "marks":         2,                <- Integer: 2, 5, 10, or 15
  "difficulty":    "easy",           <- Exactly: easy | medium | hard
  "question_type": "short",          <- Exactly: short (2M) | brief (5M) | long (10M) | essay (15M)
  "image_path":    null              <- null, or a valid relative path from ACADEMIC FIGURES section
}

question_type mapping (STRICT - no exceptions):
  - 2-mark  -> "short"
  - 5-mark  -> "brief"
  - 10-mark -> "long"
  - 15-mark -> "essay"

================================================
QUESTION QUALITY RULES
================================================
1. GROUNDING - Every question MUST be directly grounded in the provided syllabus topics
   and source material. Do NOT invent facts, theories, formulas, or concepts that are
   not explicitly present in the provided content.

2. UNIQUENESS - Every question MUST test a distinct concept. Do not generate two questions
   that test the same idea with different numbers or slight rewording.

3. COMPLETENESS - Every question must be self-contained. A student must be able to answer
   it without any external reference not provided in the exam paper.

4. PROPORTIONALITY - Question depth must match marks:
   - 2-mark  (short):  One focused concept. Answerable in 2-3 sentences.
   - 5-mark  (brief):  2-3 key points required. Requires explanation or computation.
   - 10-mark (long):   4-6 structured points. Requires analysis or multi-step work.
   - 15-mark (essay):  6-10 key points with structure. Requires synthesis and evaluation.

5. COVERAGE - Questions MUST be distributed across ALL available syllabus units.
   No unit should have zero questions unless the total question count forces it.

6. CLARITY - Questions must be unambiguous. One clear question per item.
   No double-barreled questions (e.g., "Explain X and also derive Y" is ONE question only
   if both X and Y relate tightly; otherwise split them or pick one).

================================================
TEXT FORMATTING RULES
================================================
- Plain text ONLY. No LaTeX, no Markdown, no backslash math commands.
- Mathematical expressions in plain text:
    - Multiplication: * or x
    - Division: /
    - Subscripts: x_1, x_2
    - Superscripts/powers: x^2, e^(x)
    - Fractions: (a)/(b)
    - Matrices: [[1,2],[3,4]]
    - Integrals: integral(a to b) f(x) dx
    - Summations: sum(i=1 to n) x_i
    - Inequalities: <=, >=, !=
    - Greek: alpha, beta, gamma, delta, lambda, mu, sigma, pi, theta, omega

================================================
================================================
IMAGE / FIGURE RULES (SELECTIVE GENERATION)
================================================
- Include images ONLY when necessary (e.g., Circuit diagrams, Graphs, Geometric figures, Biological/Chemical structures, Flowcharts).
- Priority Order:
    1. Table -> when structured values or datasets are sufficient.
    2. Text -> when no visual aid is required.
    3. Image -> ONLY when a visual representation is essential for solving or understanding the question.
- Do NOT generate images for:
    - Theory questions
    - Definition-based questions
    - Derivation questions
    - Essay or descriptive questions
    - Conceptual or explanation-based questions where text alone is sufficient
- If ACADEMIC FIGURES section is empty or absent: image_path MUST be null for ALL questions.
- If figures are listed in ACADEMIC FIGURES, you may optionally use them:
    - Set image_path to the exact relative_path shown in the figure entry.
    - The question text MUST reference the figure generically (e.g., "the figure shown", "the diagram shown", "the graph shown").
    - NEVER mention image IDs or filenames inside the question text.
- When image_path is null: do NOT reference any figure in the question text.

================================================
ANTI-HALLUCINATION GUARDRAILS
================================================
- If a topic has insufficient source material to generate a quality question, generate a
  simpler recall/definition question about that topic instead of inventing content.
- Never claim the source material says something it does not say.
- Never generate questions about authors, researchers, or publications not in the source.
- Never use real institution names, real student names, or real product names unless
  they appear verbatim in the source material.
"""


# -----------------------------------------------------------------------------
# USER PROMPT TEMPLATE
# -----------------------------------------------------------------------------

QUESTION_USER_PROMPT_TEMPLATE = """\
Generate a complete university examination question paper from the materials below.

==============================================
SYLLABUS TOPICS
==============================================
{syllabus_topics_text}

==============================================
RETRIEVED SOURCE MATERIAL
==============================================
{content_context}
{academic_figures_section}
==============================================
EXAMINATION BLUEPRINT (MANDATORY - EXACT)
==============================================
Total Marks:           {total_marks}
Total Questions:       {total_questions}
  - 2-mark  questions: {two_mark_count}   (type: "short")
  - 5-mark  questions: {five_mark_count}   (type: "brief")
  - 10-mark questions: {ten_mark_count}   (type: "long")
  - 15-mark questions: {fifteen_mark_count}  (type: "essay")

Target difficulty distribution:
  - easy:   {easy_pct}%
  - medium: {medium_pct}%
  - hard:   {hard_pct}%
{subject_profile_section}
==============================================
GENERATION CONTRACT - FOLLOW EXACTLY
==============================================
1. Generate EXACTLY {total_questions} questions - no more, no fewer.
2. Generate EXACTLY {two_mark_count} questions with marks=2.
3. Generate EXACTLY {five_mark_count} questions with marks=5.
4. Generate EXACTLY {ten_mark_count} questions with marks=10.
5. Generate EXACTLY {fifteen_mark_count} questions with marks=15.
6. Total marks must sum to {total_marks}.
7. IDs must be sequential: Q001, Q002, Q003, ... Q{total_questions:03d}.
8. Every question must be traceable to a specific unit and topic from the syllabus above.
9. Every question must be grounded in the source material - do NOT invent content.
10. Do NOT repeat the same concept across multiple questions.
11. Distribute questions across ALL units - do not cluster in one unit.
12. If ACADEMIC FIGURES are listed above: you may optionally generate questions using the figures if they meet the strict IMAGE RULES. Set image_path to the exact relative_path shown if you use one.
13. Output ONLY the JSON array. No explanation, no preamble, no markdown.
14. Stop immediately after the final ] - do not write anything after it.
"""


# -----------------------------------------------------------------------------
# CORRECTION ADDENDUM (appended on retry attempts)
# -----------------------------------------------------------------------------

QUESTION_CORRECTION_ADDENDUM_TEMPLATE = """\

==============================================
VALIDATION ERRORS FROM PREVIOUS ATTEMPT
==============================================
Your previous output was REJECTED for the following reasons:
{issues}

You MUST fix ALL of the above errors in your next output.

STRICT REQUIREMENTS FOR CORRECTION:
- Return a COMPLETE, corrected JSON array - not just the fixed questions.
- The corrected array MUST still satisfy exactly:
    Total Marks:    {total_marks}
    Total Questions: {total_questions}
    2-mark:  {two_mark_count}  |  5-mark: {five_mark_count}  |  10-mark: {ten_mark_count}  |  15-mark: {fifteen_mark_count}
- Do NOT explain your corrections. Output ONLY the corrected JSON array.
- Preserve all valid questions from the previous attempt where possible.
- Only replace or fix the questions that caused the validation errors.
"""


# -----------------------------------------------------------------------------
# Builder functions
# -----------------------------------------------------------------------------

def _build_academic_figures_section(image_topic_map: dict) -> str:
    """
    Build the ACADEMIC FIGURES prompt section from image_topic_map.

    Each entry shows the image_id, relative_path (for image_path field),
    concept, components, and ready-to-use exam question hints.

    Returns empty string if no images are available.
    """
    if not image_topic_map:
        return ""

    lines = [
        "",
        "==============================================",
        "ACADEMIC FIGURES - USE THESE IN QUESTIONS",
        "==============================================",
        "The following academic diagrams/figures were extracted from the uploaded document.",
        "You MAY optionally use these figures to generate questions if they meet the strict IMAGE RULES.",
        "",
    ]

    for img_id, entry in image_topic_map.items():
        rel_path = entry.get("image_path", "")
        concept = entry.get("concept", "")
        components = entry.get("components", "")
        objective = entry.get("learning_objective", "")
        exam_q1 = entry.get("exam_q1", "")
        exam_q2 = entry.get("exam_q2", "")
        unit_hint = entry.get("unit_hint", "")

        lines.append(f"FIGURE [{img_id}]")
        lines.append(f"  image_path (use this EXACTLY in the JSON field): {rel_path}")
        lines.append(f"  concept:             {concept}")
        if unit_hint:
            lines.append(f"  likely_unit:         {unit_hint}")
        if components:
            lines.append(f"  key_components:      {components}")
        if objective:
            lines.append(f"  learning_objective:  {objective}")
        if exam_q1:
            lines.append(f"  suggested_exam_q1:   {exam_q1}")
        if exam_q2:
            lines.append(f"  suggested_exam_q2:   {exam_q2}")
        lines.append("")

    lines.append("NOTE: image_path in your JSON output MUST match the path shown above exactly.")
    lines.append("      The question text must say 'the figure shown', 'the diagram shown', etc.")
    lines.append("")

    return "\n".join(lines)


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
    subject_profile_section: str = "",
    image_topic_map: dict | None = None,
) -> str:
    """
    Build the user prompt for question generation.

    Args:
        syllabus_topics:       List of SyllabusTopic dicts from state.
        content_context:       RAG-retrieved source material for grounding.
                               Capped at 6000 chars to prevent token overflow.
        total_marks:           Total exam marks.
        total_questions:       Total questions to generate.
        two_mark_count:        Number of 2-mark questions.
        five_mark_count:       Number of 5-mark questions.
        ten_mark_count:        Number of 10-mark questions.
        fifteen_mark_count:    Number of 15-mark questions.
        easy_pct:              Target percentage of easy questions.
        medium_pct:            Target percentage of medium questions.
        hard_pct:              Target percentage of hard questions.
        available_image_ids:   (Legacy - ignored; use image_topic_map instead)
        subject_profile_section: Formatted subject profile addendum from SubjectPromptBuilder.
        image_topic_map:       Structured Gemini image analysis from ImageDescriptorAgent.

    Returns:
        Complete formatted user prompt string.
    """
    topics_lines: list[str] = []
    for unit in syllabus_topics:
        topics_lines.append(f"Unit {unit['unit_number']}: {unit['unit_name']}")
        for topic in unit["topics"]:
            topics_lines.append(f"  - {topic}")

    # Cap context to prevent token overflow (Fix #2)
    MAX_CONTEXT_CHARS = 6000
    context_text = content_context.strip() or "(No source material available - use syllabus topics only)"
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS] + "\n...[content truncated for token efficiency]"

    # Wrap the profile section for clear visual separation if present
    profile_section_text = ""
    if subject_profile_section and subject_profile_section.strip():
        profile_section_text = f"\n{subject_profile_section.strip()}\n"

    # Build the academic figures section from image_topic_map (Fix #4 + #6)
    academic_figures_section = _build_academic_figures_section(image_topic_map or {})

    return QUESTION_USER_PROMPT_TEMPLATE.format(
        syllabus_topics_text="\n".join(topics_lines) or "(No syllabus topics provided)",
        content_context=context_text,
        academic_figures_section=academic_figures_section,
        total_marks=total_marks,
        total_questions=total_questions,
        two_mark_count=two_mark_count,
        five_mark_count=five_mark_count,
        ten_mark_count=ten_mark_count,
        fifteen_mark_count=fifteen_mark_count,
        easy_pct=easy_pct,
        medium_pct=medium_pct,
        hard_pct=hard_pct,
        subject_profile_section=profile_section_text,
    )


def build_question_correction_addendum(
    issues: list[str],
    total_marks: int,
    total_questions: int,
    two_mark_count: int,
    five_mark_count: int,
    ten_mark_count: int,
    fifteen_mark_count: int,
) -> str:
    """Build a correction block appended to the prompt on retry attempts."""
    issues_text = "\n".join(f"  - {issue}" for issue in issues)
    return QUESTION_CORRECTION_ADDENDUM_TEMPLATE.format(
        issues=issues_text,
        total_marks=total_marks,
        total_questions=total_questions,
        two_mark_count=two_mark_count,
        five_mark_count=five_mark_count,
        ten_mark_count=ten_mark_count,
        fifteen_mark_count=fifteen_mark_count,
    )
