import json

import pytest

from app.services.llm_service import LLMService
from app.services.question_generation_errors import JSONRepairError


def test_repair_json_control_characters_only_changes_string_values() -> None:
    raw = '[\n  {"answer": "First line\nSecond\tline\u000b"}\n]'

    repaired = LLMService.repair_json_control_characters(raw)

    assert repaired == '[\n  {"answer": "First line\\nSecond\\tline\\u000b"}\n]'
    assert json.loads(repaired)[0]["answer"] == "First line\nSecond\tline\u000b"


def test_repair_json_control_characters_respects_escaped_quotes() -> None:
    raw = '{"answer": "A \\"quoted\\" value\nnext"}'

    repaired = LLMService.repair_json_control_characters(raw)

    assert repaired == '{"answer": "A \\"quoted\\" value\\nnext"}'
    assert json.loads(repaired)["answer"] == 'A "quoted" value\nnext'


def test_parse_json_response_extracts_array_from_extra_explanation() -> None:
    raw = 'Here is the JSON you requested:\n[{"id":"Q001","question":"What is 2×3?"}]\nThanks.'

    parsed, meta = LLMService.parse_json_response(raw, agent_name="TestAgent")

    assert parsed == [{"id": "Q001", "question": "What is 2×3?"}]
    assert meta["response_length"] == len(raw)
    assert meta["extracted_length"] == len('[{"id":"Q001","question":"What is 2×3?"}]')


def test_parse_json_response_repairs_invalid_escape_sequence() -> None:
    raw = r'[{"id":"Q001","question":"Evaluate 2 \times 3"}]'

    parsed, meta = LLMService.parse_json_response(raw, agent_name="TestAgent")

    assert parsed[0]["question"] == "Evaluate 2 times 3"
    assert meta["repair_applied"] is True


def test_parse_json_response_repairs_truncated_json_array() -> None:
    raw = '[{"id":"Q001","question":"Define force","marks":2'

    parsed, meta = LLMService.parse_json_response(raw, agent_name="TestAgent")

    assert parsed[0]["id"] == "Q001"
    assert meta["repair_applied"] is True


def test_parse_json_response_strips_markdown_code_fences() -> None:
    raw = '```json\n[{"id":"Q001","question":"State Ohm\'s law."}]\n```'

    parsed, _ = LLMService.parse_json_response(raw, agent_name="TestAgent")

    assert parsed == [{"id": "Q001", "question": "State Ohm's law."}]


def test_extract_json_array_raises_when_no_array_present() -> None:
    with pytest.raises(JSONRepairError):
        LLMService.extract_json_array("No JSON here.")
