# How to Add a New Subject Profile

This document explains how to extend the Subject Profile System with a new academic
subject **without modifying any Python code**.

---

## Step 1: Create the YAML Profile File

Add a new file to:
```
backend/app/subject_profiles/profiles/<subject_slug>.yaml
```

**Naming rules:**
- Use **lowercase** and **underscores** for spaces.
- Examples: `data_science.yaml`, `artificial_intelligence.yaml`, `history.yaml`, `law.yaml`

---

## Step 2: Fill in the YAML Profile

Copy the template below and fill in the fields for your subject:

```yaml
# ============================================================
# <Subject Name> Subject Profile
# ============================================================

subject_name: Data Science
description: >
  One-sentence description of what this subject covers.

question_styles:
  - conceptual_explanation       # How to explain a concept
  - numerical_problem            # Calculation/algorithm question
  - case_study_analysis          # Real-world scenario question
  - compare_and_contrast         # Compare two approaches
  - algorithm_design_and_trace   # Design an algorithm, trace it
  - diagram_based                # Questions about figures/charts

blooms_preferences:
  - Apply         # Must be one of: Remember, Understand, Apply, Analyze, Evaluate, Create
  - Analyze
  - Evaluate

difficulty_distribution:
  easy: 30       # Must sum to 100
  medium: 45
  hard: 25

question_guidelines:
  - "2-mark questions: ..."
  - "5-mark questions: ..."
  - "10-mark questions: ..."
  - "15-mark questions: ..."
  - "Any other specific rules for this subject."

answer_guidelines:
  - "How model answers should be structured for this subject."
  - "E.g., 'Show all calculation steps for numerical questions'."

preferred_action_verbs:
  - Define
  - Explain
  - Analyze
  - Compare
  - Calculate

forbidden_patterns:
  - "Fill in the blank"
  - "True or False"
  - "Multiple choice"
  - "Any other patterns you want to ban"

numerical_required: false   # true = at least one numerical question is mandatory
diagram_required: false     # true = at least one diagram question is mandatory

subject_specific_instructions:
  - "Any subject-domain-specific rule injected verbatim into the LLM prompt."
  - "E.g., for data science: 'Always specify the dataset schema before questions about SQL or pandas'."

prompt_template_override: null  # Leave null unless you want a fully custom user prompt
```

---

## Step 3: (Optional) Add Alias Mappings

If you want common course name variants to automatically resolve to your profile,
add them to the `_SLUG_ALIASES` dictionary in:

```
backend/app/subject_profiles/loader.py
```

Example:
```python
"data science": "data_science",
"ds": "data_science",
"machine learning": "data_science",
"big data": "data_science",
```

> **Note:** Even without aliases, if the course_name exactly matches `data_science`
> (with underscores), it will resolve automatically. Aliases are only needed for
> common alternative names.

---

## Step 4: Done — No Code Changes Required

The `SubjectProfileLoader` automatically discovers all `*.yaml` files in the
`profiles/` directory. When a paper is generated with a matching course name,
the new profile is loaded and applied.

---

## Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subject_name` | string | ✅ | Human-readable subject name |
| `description` | string | ✅ | One-line subject domain description |
| `question_styles` | list[str] | Optional | Preferred question formats |
| `blooms_preferences` | list[str] | Optional | Bloom levels to emphasise |
| `difficulty_distribution` | object | Optional | easy/medium/hard % (must sum to 100) |
| `question_guidelines` | list[str] | Optional | Per-mark-band question rules |
| `answer_guidelines` | list[str] | Optional | Model answer structure rules |
| `preferred_action_verbs` | list[str] | Optional | Verbs suitable for this subject |
| `forbidden_patterns` | list[str] | Optional | Question patterns to prohibit |
| `numerical_required` | bool | Optional | Mandate at least 1 numerical question |
| `diagram_required` | bool | Optional | Mandate at least 1 diagram question |
| `subject_specific_instructions` | list[str] | Optional | Domain rules injected verbatim |
| `prompt_template_override` | string or null | Optional | Full custom user prompt template |

---

## Fallback Behavior

If no matching YAML file is found for a course name, the system **automatically**
loads `generic.yaml`. You do not need to handle this case manually.

The `generic.yaml` profile is designed to handle:
- Artificial Intelligence / Machine Learning
- Data Science / Analytics
- Natural Language Processing / Deep Learning
- Management / Business Administration
- Social Sciences / Humanities
- Law / Ethics / Philosophy
- Any other subject not in the dedicated profiles list

---

## Available Profiles

| File | Subject |
|------|---------|
| `physics.yaml` | Physics |
| `chemistry.yaml` | Chemistry |
| `mathematics.yaml` | Mathematics |
| `biology.yaml` | Biology |
| `computer_science.yaml` | Computer Science |
| `electronics.yaml` | Electronics |
| `mechanical.yaml` | Mechanical Engineering |
| `civil.yaml` | Civil Engineering |
| `economics.yaml` | Economics |
| `generic.yaml` | **Universal fallback** (AI/ML, Data Science, Management, etc.) |
