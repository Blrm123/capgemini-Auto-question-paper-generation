"""
services/llm_service.py

Central LLM service for the Agentic Question Paper Generator.

Provider Selection (automatic):
  - PRIMARY:  Google Gemini Flash 1.5  (when GEMINI_API_KEY is set in .env)
              1M token context, native multimodal vision, fast, cheap
  - FALLBACK: Groq llama-3.3-70b-versatile (when GEMINI_API_KEY is empty)

All agents call call_llm() and call_llm_for_json() - these work identically
regardless of which provider is active underneath.

describe_image() uses Gemini's native vision when Gemini is the provider,
or falls back to Groq Qwen vision otherwise.
"""

import json
import re
import time
import warnings
from typing import Any, Optional

warnings.filterwarnings("ignore", category=UserWarning, module="langchain_google_genai")

try:
    from json_repair import repair_json
except ImportError:
    def repair_json(payload: str) -> str:
        return payload

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.services.logger import log_token_usage, setup_logger
from app.services.question_generation_errors import JSONRepairError

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Provider detection - evaluated once at import time
# ---------------------------------------------------------------------------
_USE_GEMINI: bool = settings.gemini.is_available()


def _log_provider() -> None:
    if _USE_GEMINI:
        logger.info(
            f"LLMService: PRIMARY provider = GEMINI ({settings.gemini.GEMINI_MODEL_NAME}). "
            "Groq available as fallback."
        )
    else:
        logger.info(
            f"LLMService: PRIMARY provider = GROQ ({settings.llm.MODEL_NAME}). "
            "Set GEMINI_API_KEY in .env to use Gemini Flash."
        )


_log_provider()


# ---------------------------------------------------------------------------
# Lazy model factories
# ---------------------------------------------------------------------------

def _make_gemini_model(model_name: Optional[str] = None) -> Any:
    """Instantiate a ChatGoogleGenerativeAI model (lazy import)."""
    from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
    name = model_name or settings.gemini.GEMINI_MODEL_NAME
    kwargs: dict[str, Any] = {
        "model": name,
        "google_api_key": settings.gemini.GEMINI_API_KEY,
    }
    # Omit sampling parameters for lite models to prevent fixed sampling UserWarning
    if "lite" not in name.lower():
        kwargs["temperature"] = settings.llm.TEMPERATURE
        kwargs["top_p"] = settings.llm.TOP_P
    return ChatGoogleGenerativeAI(**kwargs)


def _make_groq_model(model_name: Optional[str] = None, max_tokens: Optional[int] = None) -> Any:
    """Instantiate a ChatGroq model (lazy import)."""
    from langchain_groq import ChatGroq  # noqa: PLC0415
    name = model_name or settings.llm.MODEL_NAME
    api_key = (settings.llm.GROQ_API_KEY or "").strip()
    if not api_key:
        raise EnvironmentError(
            "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured. "
            "Please add at least one API key to your .env file."
        )
    is_large = "3.3" in name.lower() or "70b" in name.lower()
    tokens = max_tokens or (
        settings.llm.QUESTION_GENERATION_MAX_COMPLETION_TOKENS
        if is_large
        else max(4096, min(settings.llm.QUESTION_GENERATION_MAX_COMPLETION_TOKENS, 8192))
    )
    model_args: dict[str, Any] = {
        "model": name,
        "groq_api_key": api_key,
        "temperature": settings.llm.TEMPERATURE,
        "top_p": settings.llm.TOP_P,
        "max_tokens": tokens,
    }
    if "qwen" in name.lower():
        model_args["reasoning_effort"] = "none"
    return ChatGroq(**model_args)


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class LLMService:
    """
    Unified LLM service: Gemini Flash 1.5 (primary) or Groq (fallback).

    All agents use:
      call_llm()           -> raw string response
      call_llm_for_json()  -> parsed Python object (dict or list)
      describe_image()     -> structured image analysis text
    """

    def __init__(self) -> None:
        self._last_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        provider = "GEMINI" if _USE_GEMINI else "GROQ"
        logger.info(f"LLMService initialized - provider: {provider}")

    # ------------------------------------------------------------------
    # Public: text generation
    # ------------------------------------------------------------------

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "UnknownAgent",
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """Send a prompt to the active provider and return the response text."""
        if _USE_GEMINI:
            return self._call_gemini(system_prompt, user_prompt, agent_name, model_name)
        return self._call_groq(system_prompt, user_prompt, agent_name, max_tokens, model_name)

    def call_llm_for_json(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "UnknownAgent",
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> Any:
        """Call the LLM and parse the response as JSON (handles arrays and objects)."""
        raw = self.call_llm(
            system_prompt, user_prompt, agent_name,
            max_tokens=max_tokens, model_name=model_name
        )
        try:
            parsed, _ = self.parse_json_response(raw, agent_name=agent_name)
            logger.info(f"[{agent_name}] JSON parsed successfully.")
            return parsed
        except JSONRepairError as exc:
            logger.error(
                f"[{agent_name}] JSON parse failed.\nRaw:\n{raw}\nError: {exc}"
            )
            raise ValueError(
                f"[{agent_name}] LLM returned invalid JSON: {exc}\nResponse:\n{raw}"
            ) from exc

    def get_last_usage(self) -> dict[str, int]:
        return dict(self._last_usage)

    # ------------------------------------------------------------------
    # Public: vision / image description
    # ------------------------------------------------------------------

    def describe_image(self, image_path: str, syllabus_context: str = "") -> str:
        """
        Analyze an academic image and return a structured educational description.

        Uses Gemini native multimodal vision when Gemini is the active provider.
        Falls back to Groq Qwen vision when only Groq is configured.

        Args:
            image_path:       Absolute path to the image file on disk.
            syllabus_context: Optional course/topic context to guide analysis.

        Returns:
            Structured educational analysis string (CONCEPT / COMPONENTS / etc.)
        """
        if _USE_GEMINI:
            return self._describe_image_gemini(image_path, syllabus_context)
        return self._describe_image_groq(image_path)

    # ------------------------------------------------------------------
    # Private: Gemini calls
    # ------------------------------------------------------------------

    def _call_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str,
        model_name: Optional[str] = None,
    ) -> str:
        """Call Google Gemini with retry logic."""
        max_retries = settings.llm.MAX_RETRIES
        retry_delay = settings.llm.RETRY_DELAY_SECONDS
        last_exc: Optional[Exception] = None

        target_model = model_name or settings.gemini.get_model_for_agent(agent_name)
        for attempt in range(1, max_retries + 1):
            try:
                model = _make_gemini_model(target_model)
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
                logger.info(
                    f"[{agent_name}] Gemini ({target_model}) "
                    f"attempt {attempt}/{max_retries}..."
                )
                response = model.invoke(messages)
                self._log_usage(response, agent_name)
                content = response.content
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, str):
                            text_parts.append(block)
                        elif isinstance(block, dict) and "text" in block:
                            text_parts.append(str(block["text"]))
                    content = "\n".join(text_parts)
                elif not isinstance(content, str):
                    content = str(content)

                if not content or not content.strip():
                    raise ValueError("Gemini returned an empty response.")
                logger.info(f"[{agent_name}] Gemini call succeeded.")
                return content.strip()
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    f"[{agent_name}] Gemini attempt {attempt} failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < max_retries:
                    wait = min(5.0, retry_delay * attempt)
                    logger.info(f"[{agent_name}] Retrying in {wait:.1f}s...")
                    time.sleep(wait)

        raise RuntimeError(
            f"[{agent_name}] All {max_retries} Gemini attempts failed. "
            f"Last error: {last_exc}"
        )

    def _describe_image_gemini(self, image_path: str, syllabus_context: str = "") -> str:
        """Describe an academic image using Gemini's native multimodal vision."""
        import base64
        import os

        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "webp", "gif") else "image/png"

        ctx = (
            f"\nCourse context (for relevance): {syllabus_context[:400]}"
            if syllabus_context else ""
        )

        prompt = (
            "You are an expert academic content analyst. "
            "Analyze this educational diagram or figure from a university course."
            f"{ctx}\n\n"
            "Respond in this EXACT labeled format (be specific, educational):\n\n"
            "CONCEPT: [The main academic concept or process shown - 1 line]\n"
            "UNIT_HINT: [Which course unit/module this most likely belongs to - 1 line]\n"
            "COMPONENTS: [Key labeled parts or elements visible - comma-separated list]\n"
            "LEARNING_OBJECTIVE: [What a student must understand from this - 1 sentence]\n"
            "EXAM_Q1: [A specific 5-mark exam question that references this figure]\n"
            "EXAM_Q2: [A specific 10-mark exam question that references this figure]\n\n"
            "Do NOT describe the image purely visually - explain what it TEACHES."
        )

        messages = [
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
            ])
        ]

        try:
            target_model = settings.gemini.get_model_for_agent("PDFParser")
            model = _make_gemini_model(target_model)
            logger.info(
                f"LLMService: Gemini vision ({target_model}) -> {os.path.basename(image_path)}"
            )
            response = model.invoke(messages)
            content = response.content
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, str):
                        text_parts.append(block)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(str(block["text"]))
                content = "\n".join(text_parts)
            elif not isinstance(content, str):
                content = str(content)

            if not content or not content.strip():
                raise ValueError("Gemini vision returned empty response.")
            return content.strip()
        except Exception as exc:
            logger.error(f"Gemini vision failed for {image_path}: {exc}")
            raise RuntimeError(f"Gemini vision call failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Private: Groq calls (fallback)
    # ------------------------------------------------------------------

    def _call_groq(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str,
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """Call Groq LLM with model rotation and retry logic."""
        rotation = self._build_groq_rotation(model_name or settings.llm.MODEL_NAME)
        model_idx = 0
        current = rotation[model_idx]
        last_exc: Optional[Exception] = None
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for attempt in range(1, settings.llm.MAX_RETRIES + 1):
            try:
                model = _make_groq_model(current, max_tokens)
                logger.info(
                    f"[{agent_name}] Groq ({current}) attempt {attempt}/{settings.llm.MAX_RETRIES}..."
                )
                response = model.invoke(messages)
                self._log_usage(response, agent_name)
                content = response.content
                if not content or not str(content).strip():
                    raise ValueError("Groq returned an empty response.")
                logger.info(f"[{agent_name}] Groq call succeeded.")
                return str(content).strip()
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                logger.warning(
                    f"[{agent_name}] Groq attempt {attempt} failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                if self._should_switch_groq_model(err_str) and len(rotation) > 1:
                    model_idx = (model_idx + 1) % len(rotation)
                    next_model = rotation[model_idx]
                    if next_model != current:
                        logger.warning(
                            f"[{agent_name}] Rate limit: rotating '{current}' -> '{next_model}'"
                        )
                        current = next_model
                if attempt < settings.llm.MAX_RETRIES:
                    wait = min(3.0, settings.llm.RETRY_DELAY_SECONDS * attempt)
                    logger.info(f"[{agent_name}] Retrying Groq in {wait:.1f}s...")
                    time.sleep(wait)

        raise RuntimeError(
            f"[{agent_name}] All {settings.llm.MAX_RETRIES} Groq attempts failed. "
            f"Last error: {last_exc}"
        )

    def _describe_image_groq(self, image_path: str) -> str:
        """Describe an image using Groq Qwen vision (fallback when Gemini unavailable)."""
        import base64
        import os
        from langchain_groq import ChatGroq  # noqa: PLC0415

        api_key = (settings.llm.GROQ_API_KEY or "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")

        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "webp", "gif") else "image/png"

        prompt = (
            "You are an academic content analyst. Analyze this educational diagram/figure:\n\n"
            "CONCEPT: [main academic concept shown]\n"
            "UNIT_HINT: [likely course unit]\n"
            "COMPONENTS: [key elements visible, comma-separated]\n"
            "LEARNING_OBJECTIVE: [what a student must learn from this]\n"
            "EXAM_Q1: [a 5-mark exam question about this figure]\n"
            "EXAM_Q2: [a 10-mark exam question about this figure]"
        )
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
            ])
        ]
        vision_model = ChatGroq(
            model="qwen/qwen3.6-27b",
            groq_api_key=api_key,
            temperature=0.1,
            top_p=0.9,
            reasoning_effort="none",
        )
        logger.info(f"LLMService: Groq Qwen vision -> {os.path.basename(image_path)}")
        response = vision_model.invoke(messages)
        content = response.content
        if not content or not str(content).strip():
            raise ValueError("Groq vision returned empty response.")
        return str(content).strip()

    # ------------------------------------------------------------------
    # Private: usage logging
    # ------------------------------------------------------------------

    def _log_usage(self, response: Any, agent_name: str) -> None:
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage:
                self._last_usage = {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": (
                        usage.get("total_tokens", 0)
                        or usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    ),
                }
                log_token_usage(
                    logger=logger,
                    agent_name=agent_name,
                    prompt_tokens=self._last_usage["prompt_tokens"],
                    completion_tokens=self._last_usage["completion_tokens"],
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Private: Groq utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _build_groq_rotation(primary: str) -> list[str]:
        rotation: list[str] = []
        seen: set[str] = set()
        for name in [primary, *settings.llm.FALLBACK_MODELS]:
            c = name.strip()
            if c and c not in seen:
                seen.add(c)
                rotation.append(c)
        return rotation

    _build_model_rotation = _build_groq_rotation

    @staticmethod
    def _should_switch_groq_model(err: str) -> bool:
        return any(t in err for t in ("429", "rate_limit", "quota", "tpd",
                                      "model_decommissioned", "decommissioned"))

    _should_switch_model = _should_switch_groq_model

    # ------------------------------------------------------------------
    # Public: JSON parsing utilities (provider-agnostic)
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = text.strip()
        if "<think>" in text:
            if "</think>" in text:
                text = text.split("</think>", 1)[1].strip()
            else:
                text = text.split("<think>", 1)[0].strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[-1].strip() == "```":
                lines = lines[1:-1]
            elif lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            text = "\n".join(lines).strip()
        return text

    @classmethod
    def parse_json_response(
        cls,
        raw_response: str,
        agent_name: str = "UnknownAgent",
    ) -> tuple[Any, dict[str, Any]]:
        cleaned = cls._strip_code_fences(raw_response)
        json_payload = cls.extract_json_payload(cleaned)
        sanitized_payload = cls.repair_json_math_escapes(json_payload)
        metadata = {
            "response_length": len(raw_response),
            "extracted_length": len(json_payload),
            "repair_applied": False,
            "repair_strategy": "none",
        }
        if sanitized_payload != json_payload:
            metadata["repair_applied"] = True
            metadata["repair_strategy"] = "math_escape_cleaned"

        try:
            return json.loads(sanitized_payload), metadata
        except json.JSONDecodeError:
            repaired = cls.repair_json_payload(sanitized_payload)
            metadata["repair_applied"] = True
            metadata["repair_strategy"] = "json_repair"
        try:
            return json.loads(repaired), metadata
        except json.JSONDecodeError as exc:
            logger.error(
                f"[{agent_name}] JSON parse failed after repair. "
                f"response_length={metadata['response_length']}"
            )
            raise JSONRepairError(str(exc)) from exc

    @classmethod
    def extract_json_payload(cls, text: str) -> str:
        """
        Extract the first top-level JSON structure (object {...} or array [...]) from text.
        """
        obj_start = text.find("{")
        arr_start = text.find("[")

        if obj_start == -1 and arr_start == -1:
            raise JSONRepairError("No JSON object or array found in LLM response.")

        if obj_start != -1 and (arr_start == -1 or obj_start < arr_start):
            start = obj_start
            open_char, close_char = "{", "}"
        else:
            start = arr_start
            open_char, close_char = "[", "]"

        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            c = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    in_string = False
                continue

            if c == '"':
                in_string = True
            elif c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

        return text[start:]

    @classmethod
    def extract_json_array(cls, text: str) -> str:
        """Alias for extract_json_payload for backward compatibility."""
        return cls.extract_json_payload(text)

    @classmethod
    def repair_json_payload(cls, raw: str) -> str:
        repaired = cls.repair_json_math_escapes(raw)
        repaired = cls.repair_json_control_characters(repaired)
        repaired = cls.repair_json_invalid_escapes(repaired)
        repaired = repair_json(repaired)
        if not repaired:
            raise JSONRepairError("json-repair returned empty result.")
        return repaired

    @staticmethod
    def repair_json_invalid_escapes(raw: str) -> str:
        return re.sub(r'\\(?!["\\/bfnrtu]|u[0-9a-fA-F]{4})', "", raw)

    @staticmethod
    def repair_json_control_characters(raw: str) -> str:
        result: list[str] = []
        in_str = False
        escaped = False
        for c in raw:
            if in_str and ord(c) < 0x20:
                escapes = {"\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
                result.append(escapes.get(c, f"\\u{ord(c):04x}"))
                escaped = False
                continue
            result.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_str = not in_str
        return "".join(result)

    @staticmethod
    def repair_json_math_escapes(raw: str) -> str:
        pattern = re.compile(
            r'(?<!\\)\\(?='
            r'(?:left|right|frac|times|cdot|div|approx|geq|leq|neq|beta|theta|alpha|gamma|'
            r'delta|lambda|sigma|phi|omega|Delta|Sigma|sqrt|pi|mu|ge|le|in|to|pm|xi|'
            r'[a-zA-Z]{3,})'
            r')'
        )
        return pattern.sub("", raw)
