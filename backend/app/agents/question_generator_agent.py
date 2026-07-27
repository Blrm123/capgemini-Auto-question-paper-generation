"""
Question Generator Agent for the Agentic Question Paper Generator.
"""

from __future__ import annotations

import importlib
import re
import sys
from collections import Counter
from typing import Any, Optional

from app.config import settings
from app.models.state import AgentState, QuestionDistribution, QuestionItem
from app.prompts.question_prompt import (
    QUESTION_SYSTEM_PROMPT,
    build_question_correction_addendum,
    build_question_user_prompt,
)
from app.services.blueprint_utils import (
    MARKS_TO_QUESTION_TYPE,
    MARK_BANDS,
    VALID_MARK_VALUES,
    blueprint_mismatch_messages,
    expected_total_marks,
    expected_total_questions,
    reconcile_questions_to_blueprint,
    renumber_question_ids,
)
from app.services.llm_service import LLMService
from app.services.logger import log_execution_time, setup_logger
from app.services.question_generation_errors import (
    BlueprintMismatchError,
    JSONRepairError,
    OutputTooLargeError,
    QuestionGenerationError,
    SchemaValidationError,
)

logger = setup_logger(__name__)

AGENT_NAME = "QuestionGeneratorAgent"
QUESTION_GENERATION_MAX_TOKENS = settings.llm.QUESTION_GENERATION_MAX_COMPLETION_TOKENS
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_VALID_QUESTION_TYPES = {"short", "brief", "long", "essay"}


class QuestionGeneratorAgent:
    """Generates university-level exam questions from syllabus topics."""

    def __init__(self) -> None:
        self.llm = LLMService()
        logger.info(f"{AGENT_NAME} initialized.")

    def __call__(self, state: AgentState) -> dict[str, Any]:
        with log_execution_time(logger, AGENT_NAME):
            return self._run(state)

    def _run(self, state: AgentState) -> dict[str, Any]:
        errors: list[str] = list(state.get("errors", []))

        if state.get("status") == "failed":
            logger.warning(f"{AGENT_NAME}: Skipping because workflow status is 'failed'.")
            return {
                "generated_questions": [],
                "current_agent": AGENT_NAME,
                "status": "failed",
                "errors": errors,
            }

        syllabus_topics: list = state.get("syllabus_topics", [])
        if not syllabus_topics:
            error_msg = (
                f"{AGENT_NAME}: syllabus_topics is empty. Cannot generate questions without extracted syllabus."
            )
            logger.error(error_msg)
            errors.append(error_msg)
            return self._failure(errors)

        distribution: Optional[QuestionDistribution] = state.get("question_distribution")
        if not distribution:
            error_msg = (
                f"{AGENT_NAME}: question_distribution is not set in state. "
                "Cannot generate questions without knowing the required counts."
            )
            logger.error(error_msg)
            errors.append(error_msg)
            return self._failure(errors)

        try:
            requested_total_questions = self._validate_generation_request(distribution)
        except QuestionGenerationError as exc:
            error_msg = f"{AGENT_NAME}: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            return self._failure(errors)

        registry, available_image_ids = self._load_image_registry()
        content_context: str = state.get("content_context") or ""

        try:
            batch_specs = self._build_batch_specs(distribution, requested_total_questions)
            generated_questions = self._generate_all_batches(
                syllabus_topics=syllabus_topics,
                content_context=content_context,
                distribution=distribution,
                requested_total_questions=requested_total_questions,
                available_image_ids=available_image_ids,
                registry=registry,
                batch_specs=batch_specs,
            )
            generated_questions = renumber_question_ids(generated_questions)

            final_issues = self._validate_output(
                questions=generated_questions,
                distribution=distribution,
                registry=registry,
                allowed_image_ids=self._parse_image_ids(available_image_ids),
            )
            if final_issues:
                reconciled, reconcile_actions = reconcile_questions_to_blueprint(
                    generated_questions,
                    distribution,
                )
                for action in reconcile_actions:
                    logger.warning(f"{AGENT_NAME}: {action}")
                generated_questions = renumber_question_ids(reconciled)
                final_issues = self._validate_output(
                    questions=generated_questions,
                    distribution=distribution,
                    registry=registry,
                    allowed_image_ids=self._parse_image_ids(available_image_ids),
                )
                if final_issues:
                    raise BlueprintMismatchError("; ".join(final_issues))

            logger.info(
                f"{AGENT_NAME}: Successfully generated {len(generated_questions)} question(s) "
                f"matching blueprint ({distribution['total_marks']} marks)."
            )
            return {
                "generated_questions": generated_questions,
                "current_agent": AGENT_NAME,
                "status": "running",
                "errors": errors,
            }
        except QuestionGenerationError as exc:
            error_msg = f"{AGENT_NAME}: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            return self._failure(errors)
        except Exception as exc:
            error_msg = f"{AGENT_NAME}: Unexpected generation failure - {exc}"
            logger.exception(error_msg)
            errors.append(error_msg)
            return self._failure(errors)

    def _failure(self, errors: list[str]) -> dict[str, Any]:
        return {
            "generated_questions": [],
            "current_agent": AGENT_NAME,
            "status": "failed",
            "errors": errors,
        }

    def _validate_generation_request(self, distribution: QuestionDistribution) -> int:
        expected_questions = expected_total_questions(distribution)
        expected_marks = expected_total_marks(distribution)
        total_marks = int(distribution["total_marks"])
        difficulty_total = (
            int(distribution["easy_percentage"])
            + int(distribution["medium_percentage"])
            + int(distribution["hard_percentage"])
        )

        logger.info(
            f"{AGENT_NAME}: Requested counts - "
            f"2M={distribution['two_mark_questions']}, "
            f"5M={distribution['five_mark_questions']}, "
            f"10M={distribution['ten_mark_questions']}, "
            f"15M={distribution['fifteen_mark_questions']}, "
            f"total_questions={expected_questions}, total_marks={total_marks}"
        )

        if expected_questions <= 0:
            raise QuestionGenerationError("Requested question count must be greater than zero.")
        if expected_marks != total_marks:
            raise BlueprintMismatchError(
                f"Invalid blueprint: marks implied by question counts are {expected_marks}, expected {total_marks}."
            )
        if difficulty_total != 100:
            raise BlueprintMismatchError(
                f"Invalid difficulty distribution: percentages sum to {difficulty_total}, expected 100."
            )
        return expected_questions

    def _load_image_registry(self) -> tuple[Any, str]:
        available_image_ids = "(none)"
        registry = None
        try:
            rag_base = str(settings.paths.BASE_DIR / "rag")
            if rag_base not in sys.path:
                sys.path.insert(0, rag_base)
            module = importlib.import_module("src.ingestion.image_registry")
            image_registry = module.ImageRegistry(settings.paths.BASE_DIR)
            image_registry.load()
            academic_ids = image_registry.get_academic_ids()
            registry = image_registry
            if academic_ids:
                available_image_ids = ", ".join(academic_ids)
                logger.info(
                    f"{AGENT_NAME}: Found {len(academic_ids)} academic image(s) in registry."
                )
            else:
                logger.info(
                    f"{AGENT_NAME}: No academic images in registry. image_path will be null for all questions."
                )
        except Exception as exc:
            logger.warning(
                f"{AGENT_NAME}: Could not load image registry ({exc}). Proceeding without image grounding."
            )
        return registry, available_image_ids

    def _build_batch_specs(
        self,
        distribution: QuestionDistribution,
        total_questions: int,
    ) -> list[dict[str, int]]:
        if total_questions <= settings.llm.QUESTION_BATCH_THRESHOLD:
            return [
                {
                    "two_mark_questions": int(distribution["two_mark_questions"]),
                    "five_mark_questions": int(distribution["five_mark_questions"]),
                    "ten_mark_questions": int(distribution["ten_mark_questions"]),
                    "fifteen_mark_questions": int(distribution["fifteen_mark_questions"]),
                }
            ]

        batch_specs: list[dict[str, int]] = []
        for _, field in MARK_BANDS:
            count = int(distribution[field])
            if count > 0:
                batch_specs.append(
                    {
                        "two_mark_questions": count if field == "two_mark_questions" else 0,
                        "five_mark_questions": count if field == "five_mark_questions" else 0,
                        "ten_mark_questions": count if field == "ten_mark_questions" else 0,
                        "fifteen_mark_questions": count if field == "fifteen_mark_questions" else 0,
                    }
                )
        if not batch_specs:
            raise OutputTooLargeError("No valid batch specifications could be built.")
        logger.info(
            f"{AGENT_NAME}: total_questions={total_questions} exceeds threshold "
            f"{settings.llm.QUESTION_BATCH_THRESHOLD}; splitting generation into {len(batch_specs)} batch(es)."
        )
        return batch_specs

    def _generate_all_batches(
        self,
        syllabus_topics: list,
        content_context: str,
        distribution: QuestionDistribution,
        requested_total_questions: int,
        available_image_ids: str,
        registry: Any,
        batch_specs: list[dict[str, int]],
    ) -> list[QuestionItem]:
        merged_questions: list[QuestionItem] = []
        allowed_image_ids = self._parse_image_ids(available_image_ids)

        for batch_index, batch_counts in enumerate(batch_specs, start=1):
            batch_total_questions = sum(batch_counts.values())
            batch_total_marks = (
                batch_counts["two_mark_questions"] * 2
                + batch_counts["five_mark_questions"] * 5
                + batch_counts["ten_mark_questions"] * 10
                + batch_counts["fifteen_mark_questions"] * 15
            )
            logger.info(
                f"{AGENT_NAME}: Starting batch {batch_index}/{len(batch_specs)} - "
                f"2M={batch_counts['two_mark_questions']}, "
                f"5M={batch_counts['five_mark_questions']}, "
                f"10M={batch_counts['ten_mark_questions']}, "
                f"15M={batch_counts['fifteen_mark_questions']}, "
                f"total_questions={batch_total_questions}"
            )

            prompt = build_question_user_prompt(
                syllabus_topics=syllabus_topics,
                content_context=content_context,
                total_marks=batch_total_marks,
                total_questions=batch_total_questions,
                two_mark_count=batch_counts["two_mark_questions"],
                five_mark_count=batch_counts["five_mark_questions"],
                ten_mark_count=batch_counts["ten_mark_questions"],
                fifteen_mark_count=batch_counts["fifteen_mark_questions"],
                easy_pct=int(distribution["easy_percentage"]),
                medium_pct=int(distribution["medium_percentage"]),
                hard_pct=int(distribution["hard_percentage"]),
                available_image_ids=available_image_ids,
            )

            batch_questions = self._generate_batch_with_retries(
                prompt=prompt,
                batch_counts=batch_counts,
                batch_total_marks=batch_total_marks,
                batch_total_questions=batch_total_questions,
                available_image_ids=allowed_image_ids,
                registry=registry,
            )
            merged_questions.extend(batch_questions)

        logger.info(
            f"{AGENT_NAME}: Generated counts before final renumber - "
            f"{dict(Counter(int(question['marks']) for question in merged_questions))}"
        )
        merged_questions = renumber_question_ids(merged_questions)
        final_issues = self._validate_output(
            questions=merged_questions,
            distribution=distribution,
            registry=registry,
            allowed_image_ids=allowed_image_ids,
        )
        if final_issues:
            raise BlueprintMismatchError("; ".join(final_issues))
        if len(merged_questions) != requested_total_questions:
            raise BlueprintMismatchError(
                f"Generated {len(merged_questions)} questions, expected {requested_total_questions}."
            )
        return merged_questions

    def _generate_batch_with_retries(
        self,
        prompt: str,
        batch_counts: dict[str, int],
        batch_total_marks: int,
        batch_total_questions: int,
        available_image_ids: set[str],
        registry: Any,
    ) -> list[QuestionItem]:
        retry_errors: list[str] = []

        for attempt in range(1, settings.llm.QUESTION_BATCH_MAX_RETRIES + 1):
            current_prompt = prompt
            if retry_errors:
                current_prompt += build_question_correction_addendum(
                    issues=retry_errors,
                    total_marks=batch_total_marks,
                    total_questions=batch_total_questions,
                    two_mark_count=batch_counts["two_mark_questions"],
                    five_mark_count=batch_counts["five_mark_questions"],
                    ten_mark_count=batch_counts["ten_mark_questions"],
                    fifteen_mark_count=batch_counts["fifteen_mark_questions"],
                )

            raw_response = self.llm.call_llm(
                system_prompt=QUESTION_SYSTEM_PROMPT,
                user_prompt=current_prompt,
                agent_name=AGENT_NAME,
                max_tokens=QUESTION_GENERATION_MAX_TOKENS,
            )
            usage = self.llm.get_last_usage()
            logger.info(
                f"{AGENT_NAME}: batch retry={attempt} "
                f"response_length={len(raw_response)} token_usage={usage}"
            )

            try:
                parsed, parse_meta = self.llm.parse_json_response(raw_response, agent_name=AGENT_NAME)
                logger.info(
                    f"{AGENT_NAME}: repair_status={parse_meta['repair_applied']} "
                    f"repair_strategy={parse_meta['repair_strategy']} "
                    f"extracted_length={parse_meta['extracted_length']}"
                )
            except JSONRepairError as exc:
                retry_errors = [f"Invalid JSON response: {exc}"]
                logger.warning(
                    f"{AGENT_NAME}: batch retry={attempt} validation_status=json_repair_failed"
                )
                continue

            if not isinstance(parsed, list):
                retry_errors = ["Output must be a JSON array of question objects."]
                logger.warning(
                    f"{AGENT_NAME}: batch retry={attempt} validation_status=not_array"
                )
                continue

            try:
                questions = self._parse_llm_questions(parsed, registry=registry)
                validation_distribution = {
                    "total_marks": batch_total_marks,
                    "two_mark_questions": batch_counts["two_mark_questions"],
                    "five_mark_questions": batch_counts["five_mark_questions"],
                    "ten_mark_questions": batch_counts["ten_mark_questions"],
                    "fifteen_mark_questions": batch_counts["fifteen_mark_questions"],
                    "easy_percentage": 0,
                    "medium_percentage": 0,
                    "hard_percentage": 0,
                }
                retry_errors = self._validate_output(
                    questions=questions,
                    distribution=validation_distribution,
                    registry=registry,
                    allowed_image_ids=available_image_ids,
                    validate_difficulty_distribution=False,
                )
                if retry_errors:
                    logger.warning(
                        f"{AGENT_NAME}: batch retry={attempt} validation_status=failed "
                        f"errors={' | '.join(retry_errors)}"
                    )
                    continue

                logger.info(
                    f"{AGENT_NAME}: batch retry={attempt} validation_status=passed "
                    f"generated_counts={dict(Counter(int(q['marks']) for q in questions))}"
                )
                return questions
            except SchemaValidationError as exc:
                retry_errors = [str(exc)]
                logger.warning(
                    f"{AGENT_NAME}: batch retry={attempt} validation_status=schema_failed"
                )

        raise QuestionGenerationError(
            f"Could not produce a valid question batch after "
            f"{settings.llm.QUESTION_BATCH_MAX_RETRIES} attempts. "
            f"Validation errors: {'; '.join(retry_errors)}"
        )

    def _parse_llm_questions(
        self,
        raw_data: list[Any],
        registry: Any,
    ) -> list[QuestionItem]:
        generated_questions: list[QuestionItem] = []
        parse_errors: list[str] = []

        for idx, item in enumerate(raw_data):
            if not isinstance(item, dict):
                parse_errors.append(f"Item at index {idx} is not an object.")
                continue

            q_id = item.get("id")
            unit = item.get("unit")
            topic = item.get("topic")
            question = item.get("question")
            marks = item.get("marks")
            difficulty = item.get("difficulty")
            question_type = item.get("question_type")
            image_path = item.get("image_path")

            if not isinstance(q_id, str) or not q_id.strip():
                parse_errors.append(f"Item {idx} is missing a valid id.")
                continue
            if not isinstance(unit, str) or not unit.strip():
                parse_errors.append(f"Item {idx} ({q_id}) is missing a valid unit.")
                continue
            if not isinstance(topic, str) or not topic.strip():
                parse_errors.append(f"Item {idx} ({q_id}) is missing a valid topic.")
                continue
            if not isinstance(question, str) or not question.strip():
                parse_errors.append(f"Item {idx} ({q_id}) is missing a valid question.")
                continue

            try:
                marks = int(marks)
            except (ValueError, TypeError):
                parse_errors.append(f"Item {idx} ({q_id}) has invalid marks: {marks}.")
                continue
            if marks not in VALID_MARK_VALUES:
                parse_errors.append(f"Item {idx} ({q_id}) has unsupported marks: {marks}.")
                continue

            if not isinstance(difficulty, str):
                parse_errors.append(f"Item {idx} ({q_id}) is missing difficulty.")
                continue
            difficulty = difficulty.strip().lower()

            if not isinstance(question_type, str):
                parse_errors.append(f"Item {idx} ({q_id}) is missing question_type.")
                continue
            question_type = question_type.strip().lower()

            if image_path is None:
                normalized_image_path = None
            elif isinstance(image_path, str) and image_path.strip():
                normalized_image_path = image_path.strip()
                if registry is not None and registry.is_valid_image_id(normalized_image_path):
                    normalized_image_path = registry.get_relative_path(normalized_image_path)
            else:
                normalized_image_path = None

            generated_questions.append(
                {
                    "id": q_id.strip(),
                    "unit": unit.strip(),
                    "topic": topic.strip(),
                    "question": question.strip(),
                    "marks": marks,
                    "difficulty": difficulty,
                    "question_type": question_type,
                    "image_path": normalized_image_path,
                }
            )

        if parse_errors:
            raise SchemaValidationError("; ".join(parse_errors))
        return generated_questions

    def _validate_output(
        self,
        questions: list[QuestionItem],
        distribution: dict[str, Any],
        registry: Any,
        allowed_image_ids: set[str],
        validate_difficulty_distribution: bool = True,
    ) -> list[str]:
        issues: list[str] = []
        issues.extend(blueprint_mismatch_messages(questions, distribution))

        expected_ids = [f"Q{index:03d}" for index in range(1, len(questions) + 1)]
        actual_ids = [str(question.get("id", "")) for question in questions]
        if actual_ids != expected_ids:
            issues.append(
                f"IDs must be sequential starting at Q001. Found: {', '.join(actual_ids[:10])}"
            )

        normalized_questions: set[str] = set()
        duplicate_questions: set[str] = set()
        for question in questions:
            difficulty = str(question.get("difficulty", "")).strip().lower()
            question_type = str(question.get("question_type", "")).strip().lower()
            marks = int(question.get("marks", 0))
            question_text = str(question.get("question", "")).strip()
            image_path = question.get("image_path")

            if difficulty not in _VALID_DIFFICULTIES:
                issues.append(
                    f"Question {question.get('id')} has invalid difficulty '{question.get('difficulty')}'."
                )
            expected_type = MARKS_TO_QUESTION_TYPE.get(marks)
            if question_type not in _VALID_QUESTION_TYPES:
                issues.append(
                    f"Question {question.get('id')} has invalid question_type '{question.get('question_type')}'."
                )
            elif expected_type and question_type != expected_type:
                issues.append(
                    f"Question {question.get('id')} must use question_type '{expected_type}' for {marks} marks."
                )

            normalized_text = re.sub(r"\s+", " ", question_text).casefold()
            if normalized_text in normalized_questions:
                duplicate_questions.add(str(question.get("id")))
            normalized_questions.add(normalized_text)

            if "```" in question_text or question_text.startswith("#"):
                issues.append(f"Question {question.get('id')} contains markdown formatting.")
            if re.search(r"\\[A-Za-z]+", question_text):
                issues.append(f"Question {question.get('id')} contains LaTeX-style commands.")

            if image_path:
                if any(image_id in question_text for image_id in allowed_image_ids):
                    issues.append(
                        f"Question {question.get('id')} must not mention image IDs inside question text."
                    )
                if not re.search(r"\b(figure|diagram|graph|circuit)\b", question_text, flags=re.IGNORECASE):
                    issues.append(
                        f"Question {question.get('id')} uses image_path but does not refer to the figure generically."
                    )
                if registry is not None:
                    relative_path = str(image_path)
                    if not (settings.paths.BASE_DIR / relative_path).is_file():
                        issues.append(
                            f"Question {question.get('id')} has invalid image_path '{image_path}'."
                        )
            else:
                if re.search(r"\bimage\s+[A-Za-z0-9_-]+\b", question_text, flags=re.IGNORECASE):
                    issues.append(
                        f"Question {question.get('id')} references a raw image identifier in the text."
                    )

        if duplicate_questions:
            issues.append(
                f"Duplicate questions detected for IDs: {', '.join(sorted(duplicate_questions))}."
            )

        if validate_difficulty_distribution:
            difficulty_counts = Counter(
                str(question.get("difficulty", "")).strip().lower()
                for question in questions
                if str(question.get("difficulty", "")).strip().lower() in _VALID_DIFFICULTIES
            )
            logger.info(
                f"{AGENT_NAME}: validation difficulty_counts={dict(difficulty_counts)} "
                f"generated_counts={dict(Counter(int(q['marks']) for q in questions))}"
            )

        return issues

    @staticmethod
    def _parse_image_ids(available_image_ids: str) -> set[str]:
        if not available_image_ids or available_image_ids == "(none)":
            return set()
        return {part.strip() for part in available_image_ids.split(",") if part.strip()}


_question_generator_agent = QuestionGeneratorAgent()


def question_generator_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph-compatible node function for the Question Generator Agent."""
    return _question_generator_agent(state)
