"""
services/llm_service.py

Central LLM service for the Agentic Question Paper Generator.
"""

import json
import re
import time
from typing import Any, Optional

try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover - fallback only when dependency is absent
    def repair_json(payload: str) -> str:
        return payload
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.config import settings
from app.services.logger import log_token_usage, setup_logger
from app.services.question_generation_errors import JSONRepairError

logger = setup_logger(__name__)


class LLMService:
    """Singleton-style wrapper around ChatGroq."""

    def __init__(self) -> None:
        self._model: Optional[ChatGroq] = None
        self._last_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        logger.info(
            f"LLMService initialized - model: {settings.llm.MODEL_NAME} | "
            f"temperature: {settings.llm.TEMPERATURE} | top_p: {settings.llm.TOP_P}"
        )

    def _initialize_model(self) -> ChatGroq:
        """Create and return a configured ChatGroq instance."""
        api_key = (settings.llm.GROQ_API_KEY or "").strip()
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. Please add it to your .env file or set it in the environment."
            )

        try:
            model = ChatGroq(**self._build_model_args(settings.llm.MODEL_NAME, api_key))
            return model
        except Exception as exc:
            logger.error(f"Failed to initialize ChatGroq: {exc}")
            raise

    def _build_model_args(self, model_name: str, api_key: str) -> dict[str, Any]:
        is_large_model = "3.3" in model_name.lower() or "70b" in model_name.lower()
        max_tokens = (
            settings.llm.QUESTION_GENERATION_MAX_COMPLETION_TOKENS
            if is_large_model
            else max(4096, min(settings.llm.QUESTION_GENERATION_MAX_COMPLETION_TOKENS, 8192))
        )
        model_args: dict[str, Any] = {
            "model": model_name,
            "groq_api_key": api_key,
            "temperature": settings.llm.TEMPERATURE,
            "top_p": settings.llm.TOP_P,
            "max_tokens": max_tokens,
        }
        if "qwen" in model_name.lower():
            model_args["reasoning_effort"] = "none"
        return model_args

    def _get_model(self, model_name: Optional[str] = None) -> ChatGroq:
        """Get the configured ChatGroq instance."""
        if model_name is not None:
            api_key = (settings.llm.GROQ_API_KEY or "").strip()
            return ChatGroq(**self._build_model_args(model_name, api_key))

        if self._model is None:
            self._model = self._initialize_model()
        return self._model

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "UnknownAgent",
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """Send a prompt to Groq and return the response text."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        model_rotation = self._build_model_rotation(model_name or settings.llm.MODEL_NAME)
        model_index = 0
        current_model_name = model_rotation[model_index]
        last_exception: Optional[Exception] = None

        for attempt in range(1, settings.llm.MAX_RETRIES + 1):
            try:
                model = self._get_model(model_name=current_model_name)
                if max_tokens is not None:
                    model = model.bind(max_tokens=max_tokens)

                logger.info(
                    f"[{agent_name}] Calling Groq API using '{current_model_name}' "
                    f"(attempt {attempt}/{settings.llm.MAX_RETRIES}) ..."
                )
                response = model.invoke(messages)
                self._log_usage(response, agent_name)

                content = response.content
                if not content or not str(content).strip():
                    raise ValueError("LLM returned an empty response.")

                logger.info(f"[{agent_name}] Groq API call succeeded.")
                return str(content).strip()

            except Exception as exc:
                last_exception = exc
                err_str = str(exc).lower()
                logger.warning(
                    f"[{agent_name}] Attempt {attempt} failed: {type(exc).__name__}: {exc}"
                )

                if self._should_switch_model(err_str) and len(model_rotation) > 1:
                    model_index = (model_index + 1) % len(model_rotation)
                    next_model = model_rotation[model_index]
                    if next_model != current_model_name:
                        logger.warning(
                            f"[{agent_name}] Switching model from '{current_model_name}' "
                            f"to '{next_model}' for next attempt."
                        )
                        current_model_name = next_model

                if attempt < settings.llm.MAX_RETRIES:
                    wait = min(3.0, settings.llm.RETRY_DELAY_SECONDS * attempt)
                    logger.info(f"[{agent_name}] Retrying in {wait:.1f}s ...")
                    time.sleep(wait)

        raise RuntimeError(
            f"[{agent_name}] All {settings.llm.MAX_RETRIES} Groq API attempts failed. "
            f"Last error: {last_exception}"
        )

    def call_llm_for_json(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "UnknownAgent",
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> Any:
        """Call the LLM and parse the response as JSON."""
        raw_response = self.call_llm(
            system_prompt,
            user_prompt,
            agent_name,
            max_tokens=max_tokens,
            model_name=model_name,
        )
        try:
            parsed, _ = self.parse_json_response(raw_response, agent_name=agent_name)
            logger.info(f"[{agent_name}] JSON response parsed successfully.")
            return parsed
        except JSONRepairError as exc:
            logger.error(
                f"[{agent_name}] Failed to parse JSON response.\n"
                f"Raw response:\n{raw_response}\n"
                f"Error: {exc}"
            )
            raise ValueError(
                f"[{agent_name}] LLM returned invalid JSON: {exc}\n"
                f"Response was:\n{raw_response}"
            ) from exc

    def get_last_usage(self) -> dict[str, int]:
        """Return token usage metadata from the last model call."""
        return dict(self._last_usage)

    def _log_usage(self, response: Any, agent_name: str) -> None:
        """Extract token usage metadata from the LLM response if available."""
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage:
                self._last_usage = {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                    or usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                }
                log_token_usage(
                    logger=logger,
                    agent_name=agent_name,
                    prompt_tokens=self._last_usage["prompt_tokens"],
                    completion_tokens=self._last_usage["completion_tokens"],
                )
        except Exception:
            pass

    @staticmethod
    def _build_model_rotation(primary_model: str) -> list[str]:
        """Primary model first, then unique fallbacks from config."""
        rotation: list[str] = []
        seen: set[str] = set()
        for name in [primary_model, *settings.llm.FALLBACK_MODELS]:
            cleaned = name.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                rotation.append(cleaned)
        return rotation

    @staticmethod
    def _should_switch_model(error_text: str) -> bool:
        """Whether to rotate to the next model before retrying."""
        if any(token in error_text for token in ("429", "rate_limit", "quota", "tpd")):
            return True
        if "model_decommissioned" in error_text or "decommissioned" in error_text:
            return True
        if "invalid_request_error" in error_text and "model" in error_text:
            return True
        return False

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove reasoning blocks and code fences from LLM responses."""
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
        """Extract, repair, and parse JSON from an LLM response."""
        cleaned = cls._strip_code_fences(raw_response)
        json_payload = cls.extract_json_array(cleaned)
        metadata = {
            "response_length": len(raw_response),
            "extracted_length": len(json_payload),
            "repair_applied": False,
            "repair_strategy": "none",
        }

        try:
            return json.loads(json_payload), metadata
        except json.JSONDecodeError:
            repaired = cls.repair_json_payload(json_payload)
            metadata["repair_applied"] = repaired != json_payload
            metadata["repair_strategy"] = "json_repair"

        try:
            return json.loads(repaired), metadata
        except json.JSONDecodeError as exc:
            logger.error(
                f"[{agent_name}] JSON parse failed after repair. "
                f"response_length={metadata['response_length']} "
                f"extracted_length={metadata['extracted_length']}"
            )
            raise JSONRepairError(str(exc)) from exc

    @classmethod
    def extract_json_array(cls, text: str) -> str:
        """Extract only the first top-level JSON array from a response."""
        start = text.find("[")
        if start < 0:
            raise JSONRepairError("No JSON array found in LLM response.")

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        return text[start:]

    @classmethod
    def repair_json_payload(cls, raw_json: str) -> str:
        """Apply targeted cleanup and json-repair to malformed JSON."""
        repaired = cls.repair_json_control_characters(raw_json)
        repaired = cls.repair_json_invalid_escapes(repaired)
        repaired = cls.repair_json_math_escapes(repaired)
        repaired = repair_json(repaired)
        if not repaired:
            raise JSONRepairError("json-repair returned an empty result.")
        return repaired

    @staticmethod
    def repair_json_invalid_escapes(raw_json: str) -> str:
        """Remove stray backslashes that are not valid JSON escape sequences."""
        return re.sub(
            r'\\(?!["\\/bfnrtu]|u[0-9a-fA-F]{4})',
            "",
            raw_json,
        )

    @staticmethod
    def repair_json_control_characters(raw_json: str) -> str:
        """Escape raw control characters that appear inside JSON string values."""
        result: list[str] = []
        in_string = False
        escaped = False

        for char in raw_json:
            if in_string and ord(char) < 0x20:
                escapes = {
                    "\b": "\\b",
                    "\f": "\\f",
                    "\n": "\\n",
                    "\r": "\\r",
                    "\t": "\\t",
                }
                result.append(escapes.get(char, f"\\u{ord(char):04x}"))
                escaped = False
                continue

            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = not in_string

        return "".join(result)

    @staticmethod
    def repair_json_math_escapes(raw_json: str) -> str:
        """Remove leftover LaTeX-style backslash commands from JSON text."""
        latex_pattern = re.compile(
            r'(?<!\\)\\(?='
            r'(?:left|right|frac|times|cdot|div|approx|geq|leq|neq|beta|theta|alpha|gamma|delta|lambda|sigma|phi|omega|Delta|Sigma|sqrt|'
            r'pi|mu|ge|le|in|to|pm|xi|'
            r'[a-zA-Z]{3,})'
            r')'
        )
        return latex_pattern.sub("", raw_json)

    def describe_image(
        self,
        image_path: str,
        prompt: str = "Describe this image or diagram in detail.",
    ) -> str:
        """Analyze an image file using Groq's vision model and return the description."""
        import base64
        import os

        api_key = (settings.llm.GROQ_API_KEY or "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")

        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime_type = (
            f"image/{ext}" if ext in ["png", "jpg", "jpeg", "webp", "gif"] else "image/png"
        )

        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded_string}"},
                    },
                ]
            )
        ]

        vision_model_name = "qwen/qwen3.6-27b"
        try:
            vision_model = ChatGroq(
                model=vision_model_name,
                groq_api_key=api_key,
                temperature=0.1,
                top_p=0.9,
            )
            logger.info(
                f"LLMService: Calling Groq Vision model ({vision_model_name}) for {image_path}..."
            )
            response = vision_model.invoke(messages)
            content = response.content
            if not content or not str(content).strip():
                raise ValueError("Vision model returned an empty response.")
            return str(content).strip()
        except Exception as exc:
            logger.error(f"Failed to describe image {image_path}: {exc}")
            raise RuntimeError(f"Vision call failed: {exc}") from exc
