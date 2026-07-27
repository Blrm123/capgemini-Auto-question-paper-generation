"""Unit tests for LLM service model rotation."""

from app.services.llm_service import LLMService


def test_build_model_rotation_deduplicates_primary_and_fallbacks():
    rotation = LLMService._build_model_rotation("llama-3.3-70b-versatile")
    assert rotation[0] == "llama-3.3-70b-versatile"
    assert len(rotation) == len(set(rotation))
    assert "mixtral-8x7b-32768" not in rotation


def test_should_switch_model_on_rate_limit_and_decommissioned():
    assert LLMService._should_switch_model("error code: 429 rate_limit_exceeded")
    assert LLMService._should_switch_model("model_decommissioned")
    assert not LLMService._should_switch_model("connection timeout")
