"""
services/analytics_service.py

Analytics Service for the Agentic Question Paper Generator.

Responsibilities:
  - Record per-paper analytics after each generation
  - Persist cumulative aggregates and individual paper records to disk
  - Expose metrics for the /analytics and /analytics/paper/* endpoints
"""

import json
import threading
from datetime import datetime, date
from typing import Any

from app.config import settings


# ---------------------------------------------------------------------------
# Valid Bloom levels (must match BloomAgent / ValidationAgent output)
# ---------------------------------------------------------------------------
_BLOOM_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
_DIFFICULTY_LEVELS = ["easy", "medium", "hard"]
_MARKS_TIERS = ["1", "2", "5", "10", "15"]


class AnalyticsService:
    _lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Default data shapes
    # -----------------------------------------------------------------------

    @classmethod
    def _default_cumulative(cls) -> dict[str, Any]:
        return {
            "total_papers": 0,
            "total_questions": 0,
            "cumulative_generation_time": 0.0,
            "bloom_distribution": {level: 0 for level in _BLOOM_LEVELS},
            "difficulty_distribution": {d: 0 for d in _DIFFICULTY_LEVELS},
            "recent_activity": {},   # date ISO string -> paper count
            "papers": [],            # list of per-paper records (latest last)
        }

    @classmethod
    def _default_paper_record(cls) -> dict[str, Any]:
        return {
            "paper_id": "",
            "generated_at": "",
            "course_name": "",
            "exam_type": "",
            "elapsed_seconds": 0.0,
            "total_questions": 0,
            "total_marks": 0,
            "bloom_distribution": {level: 0 for level in _BLOOM_LEVELS},
            "difficulty_distribution": {d: 0 for d in _DIFFICULTY_LEVELS},
            "marks_distribution": {t: 0 for t in _MARKS_TIERS},
            "unit_coverage": [],            # [{unit, count}]
            "bloom_by_difficulty": {        # {difficulty: {bloom_level: count}}
                d: {level: 0 for level in _BLOOM_LEVELS}
                for d in _DIFFICULTY_LEVELS
            },
        }

    # -----------------------------------------------------------------------
    # Persistence helpers
    # -----------------------------------------------------------------------

    @classmethod
    def _load(cls) -> dict[str, Any]:
        path = settings.paths.ANALYTICS_FILE
        if not path.exists():
            return cls._default_cumulative()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Back-fill missing keys so old data files still work
            defaults = cls._default_cumulative()
            for key, val in defaults.items():
                if key not in data:
                    data[key] = val
            # Migrate old bloom keys (e.g. "Remembering" → "Remember")
            old_to_new = {
                "Remembering": "Remember",
                "Understanding": "Understand",
                "Applying": "Apply",
                "Analyzing": "Analyze",
                "Evaluating": "Evaluate",
                "Creating": "Create",
            }
            bloom_dist = data.get("bloom_distribution", {})
            for old_key, new_key in old_to_new.items():
                if old_key in bloom_dist:
                    bloom_dist[new_key] = bloom_dist.pop(old_key, 0)
            # Ensure all standard keys exist
            for level in _BLOOM_LEVELS:
                bloom_dist.setdefault(level, 0)
            data["bloom_distribution"] = bloom_dist
            return data
        except Exception:
            return cls._default_cumulative()

    @classmethod
    def _save(cls, data: dict[str, Any]) -> None:
        path = settings.paths.ANALYTICS_FILE
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # -----------------------------------------------------------------------
    # Record a generation event
    # -----------------------------------------------------------------------

    @classmethod
    def record_generation(
        cls,
        validated_questions: list[dict],
        elapsed_seconds: float,
        paper_metadata: dict | None = None,
    ) -> str:
        """
        Record analytics for a completed generation.

        Args:
            validated_questions: List of ValidatedQuestion dicts from the pipeline.
            elapsed_seconds:     Wall-clock time for the full generation.
            paper_metadata:      PaperMetadata dict (institution, course, etc.).

        Returns:
            paper_id: A unique identifier string for this paper's record.
        """
        with cls._lock:
            data = cls._load()

            now = datetime.now()
            paper_id = now.strftime("paper_%Y%m%d_%H%M%S")

            # ----------------------------------------------------------------
            # Build per-paper record
            # ----------------------------------------------------------------
            record = cls._default_paper_record()
            record["paper_id"] = paper_id
            record["generated_at"] = now.isoformat()
            record["elapsed_seconds"] = round(elapsed_seconds, 2)
            record["total_questions"] = len(validated_questions)

            if paper_metadata:
                record["course_name"] = paper_metadata.get("course_name", "")
                record["exam_type"] = paper_metadata.get("exam_type", "")
                record["total_marks"] = paper_metadata.get("maximum_marks", 0)

            # Per-question breakdown
            unit_counts: dict[str, int] = {}

            for q in validated_questions:
                # ----- Bloom level (field: bloom_level) -----
                bloom = q.get("bloom_level", "")
                if bloom in record["bloom_distribution"]:
                    record["bloom_distribution"][bloom] += 1

                # ----- Difficulty (field: difficulty) -----
                diff = str(q.get("difficulty", "")).strip().lower()
                if diff in record["difficulty_distribution"]:
                    record["difficulty_distribution"][diff] += 1

                # ----- Marks tier -----
                marks = str(q.get("marks", ""))
                if marks in record["marks_distribution"]:
                    record["marks_distribution"][marks] += 1

                # ----- Unit coverage -----
                unit = q.get("unit", "Unknown Unit")
                unit_counts[unit] = unit_counts.get(unit, 0) + 1

                # ----- Bloom × Difficulty matrix -----
                if diff in record["bloom_by_difficulty"] and bloom in _BLOOM_LEVELS:
                    record["bloom_by_difficulty"][diff][bloom] += 1

            record["unit_coverage"] = [
                {"unit": u, "count": c}
                for u, c in sorted(unit_counts.items(), key=lambda x: -x[1])
            ]

            # ----------------------------------------------------------------
            # Update cumulative totals
            # ----------------------------------------------------------------
            data["total_papers"] += 1
            data["total_questions"] += len(validated_questions)
            data["cumulative_generation_time"] += elapsed_seconds

            for level in _BLOOM_LEVELS:
                data["bloom_distribution"][level] = (
                    data["bloom_distribution"].get(level, 0)
                    + record["bloom_distribution"][level]
                )

            for diff in _DIFFICULTY_LEVELS:
                data["difficulty_distribution"][diff] = (
                    data["difficulty_distribution"].get(diff, 0)
                    + record["difficulty_distribution"][diff]
                )

            today = date.today().isoformat()
            data["recent_activity"][today] = data["recent_activity"].get(today, 0) + 1

            # ----------------------------------------------------------------
            # Append per-paper record (keep last 100 papers max)
            # ----------------------------------------------------------------
            data["papers"].append(record)
            if len(data["papers"]) > 100:
                data["papers"] = data["papers"][-100:]

            cls._save(data)
            return paper_id

    # -----------------------------------------------------------------------
    # Query helpers
    # -----------------------------------------------------------------------

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Returns cumulative analytics metrics."""
        with cls._lock:
            data = cls._load()

        total = data["total_papers"]
        avg_time = (
            data["cumulative_generation_time"] / total if total > 0 else 0.0
        )

        sorted_activity = sorted(
            [{"date": k, "papers": v} for k, v in data["recent_activity"].items()],
            key=lambda x: x["date"],
            reverse=True,
        )[:7]

        return {
            "total_papers": total,
            "total_questions": data["total_questions"],
            "average_generation_time": round(avg_time, 2),
            "bloom_distribution": data["bloom_distribution"],
            "difficulty_distribution": data["difficulty_distribution"],
            "recent_activity": sorted_activity,
        }

    @classmethod
    def get_latest_paper_analytics(cls) -> dict[str, Any] | None:
        """Returns analytics for the most recently generated paper, or None."""
        with cls._lock:
            data = cls._load()
        papers = data.get("papers", [])
        if not papers:
            return None
        return papers[-1]

    @classmethod
    def get_paper_analytics(cls, paper_id: str) -> dict[str, Any] | None:
        """Returns analytics for a specific paper_id, or None if not found."""
        with cls._lock:
            data = cls._load()
        papers = data.get("papers", [])
        for record in reversed(papers):
            if record.get("paper_id") == paper_id:
                return record
        return None
