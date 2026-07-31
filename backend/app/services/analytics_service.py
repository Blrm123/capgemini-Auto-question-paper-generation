import json
from datetime import date
from typing import Any
import threading

from app.config import settings

class AnalyticsService:
    _lock = threading.Lock()

    @classmethod
    def _get_default_data(cls) -> dict[str, Any]:
        return {
            "total_papers": 0,
            "total_questions": 0,
            "cumulative_generation_time": 0.0,
            "bloom_distribution": {
                "Remembering": 0,
                "Understanding": 0,
                "Applying": 0,
                "Analyzing": 0,
                "Evaluating": 0,
                "Creating": 0,
            },
            "difficulty_distribution": {
                "easy": 0,
                "medium": 0,
                "hard": 0,
            },
            "recent_activity": {}  # date string -> papers count
        }

    @classmethod
    def _load(cls) -> dict[str, Any]:
        path = settings.paths.ANALYTICS_FILE
        if not path.exists():
            return cls._get_default_data()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return cls._get_default_data()

    @classmethod
    def _save(cls, data: dict[str, Any]) -> None:
        path = settings.paths.ANALYTICS_FILE
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def record_generation(cls, validated_questions: list[dict], elapsed_seconds: float) -> None:
        with cls._lock:
            data = cls._load()

            data["total_papers"] += 1
            data["total_questions"] += len(validated_questions)
            data["cumulative_generation_time"] += elapsed_seconds

            for q in validated_questions:
                bloom = q.get("cognitive_level", "")
                if bloom in data["bloom_distribution"]:
                    data["bloom_distribution"][bloom] += 1
                elif bloom.capitalize() in data["bloom_distribution"]:
                    data["bloom_distribution"][bloom.capitalize()] += 1
                
                diff = q.get("difficulty_level", "").lower()
                if diff in data["difficulty_distribution"]:
                    data["difficulty_distribution"][diff] += 1

            today = date.today().isoformat()
            data["recent_activity"][today] = data["recent_activity"].get(today, 0) + 1

            cls._save(data)

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        with cls._lock:
            data = cls._load()

        total = data["total_papers"]
        avg_time = data["cumulative_generation_time"] / total if total > 0 else 0.0

        # Sort recent activity descending by date
        sorted_activity = sorted(
            [{"date": k, "papers": v} for k, v in data["recent_activity"].items()],
            key=lambda x: x["date"],
            reverse=True
        )[:7]  # Last 7 active days

        return {
            "total_papers": total,
            "total_questions": data["total_questions"],
            "average_generation_time": round(avg_time, 2),
            "bloom_distribution": data["bloom_distribution"],
            "difficulty_distribution": data["difficulty_distribution"],
            "recent_activity": sorted_activity,
        }
