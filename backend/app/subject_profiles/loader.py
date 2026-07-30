"""
subject_profiles/loader.py

SubjectProfileLoader — discovers, loads, validates, and caches YAML subject profiles.

Design:
    - Single Responsibility: only loads and caches profiles, never generates prompts.
    - Open/Closed: new subjects are added by dropping a YAML file, no code changes.
    - Thread-safe for a single-process FastAPI server (dict-based cache).
    - Falls back to generic.yaml for any unrecognised subject without raising.

Usage:
    loader = SubjectProfileLoader()
    profile = loader.get("Physics")           # → loads physics.yaml
    profile = loader.get("AI and Machine Learning")  # → loads generic.yaml (fallback)
    profile = loader.get(None)               # → loads generic.yaml
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import ValidationError

from app.subject_profiles.models import SubjectProfile
from app.services.logger import setup_logger

logger = setup_logger(__name__)

# Absolute path to the YAML profiles directory
_PROFILES_DIR: Path = Path(__file__).resolve().parent / "profiles"

# Slug used when no matching profile is found
_GENERIC_SLUG = "generic"

# Known slug aliases — maps common course name fragments to profile slugs.
# This allows "CSE", "CS101", "Artificial Intelligence", "Machine Learning"
# to all resolve to existing profiles (or fall through to generic).
_SLUG_ALIASES: Dict[str, str] = {
    # Artificial Intelligence / Machine Learning variants
    # All of these resolve to ai_ml.yaml
    "artificial intelligence": "ai_ml",
    "machine learning": "ai_ml",
    "deep learning": "ai_ml",
    "ai": "ai_ml",
    "ml": "ai_ml",
    "ai ml": "ai_ml",
    "ai and machine learning": "ai_ml",
    "ai & ml": "ai_ml",
    "ai/ml": "ai_ml",
    "introduction to machine learning": "ai_ml",
    "applied machine learning": "ai_ml",
    "neural networks": "ai_ml",
    "deep neural networks": "ai_ml",
    "natural language processing": "ai_ml",
    "nlp": "ai_ml",
    "computer vision": "ai_ml",
    "reinforcement learning": "ai_ml",
    "data science": "ai_ml",
    "data analytics": "ai_ml",
    "big data analytics": "ai_ml",
    "pattern recognition": "ai_ml",
    "data mining": "ai_ml",
    "predictive analytics": "ai_ml",
    "statistical machine learning": "ai_ml",
    "foundation of ai": "ai_ml",
    "foundations of ai": "ai_ml",
    "intelligent systems": "ai_ml",
    "cognitive computing": "ai_ml",
    "generative ai": "ai_ml",

    # Computer Science variants
    "cs": "computer_science",
    "cse": "computer_science",
    "computer science and engineering": "computer_science",
    "computer science": "computer_science",
    "programming": "computer_science",
    "data structures": "computer_science",
    "algorithms": "computer_science",
    "software engineering": "computer_science",
    "operating systems": "computer_science",
    "database": "computer_science",
    "networking": "computer_science",
    "computer networks": "computer_science",
    "web technology": "computer_science",

    # Electronics
    "ec": "electronics",
    "ece": "electronics",
    "electronics and communication": "electronics",
    "vlsi": "electronics",
    "embedded systems": "electronics",
    "signal processing": "electronics",
    "digital electronics": "electronics",
    "analog circuits": "electronics",
    "microprocessors": "electronics",
    "control systems": "electronics",

    # Mechanical
    "me": "mechanical",
    "mech": "mechanical",
    "mechanical engineering": "mechanical",
    "thermodynamics": "mechanical",
    "fluid mechanics": "mechanical",
    "manufacturing": "mechanical",
    "machine design": "mechanical",
    "heat transfer": "mechanical",

    # Civil
    "ce": "civil",
    "civil engineering": "civil",
    "structural engineering": "civil",
    "geotechnical": "civil",
    "transportation engineering": "civil",
    "construction": "civil",

    # Physics
    "phy": "physics",
    "engineering physics": "physics",
    "applied physics": "physics",

    # Chemistry
    "chem": "chemistry",
    "engineering chemistry": "chemistry",
    "organic chemistry": "chemistry",
    "inorganic chemistry": "chemistry",
    "physical chemistry": "chemistry",
    "biochemistry": "biology",  # route to biology profile

    # Mathematics
    "math": "mathematics",
    "maths": "mathematics",
    "engineering mathematics": "mathematics",
    "statistics": "mathematics",
    "probability": "mathematics",
    "discrete mathematics": "mathematics",
    "linear algebra": "mathematics",
    "calculus": "mathematics",
    "numerical methods": "mathematics",

    # Biology
    "bio": "biology",
    "microbiology": "biology",
    "biotechnology": "biology",
    "genetics": "biology",
    "zoology": "biology",
    "botany": "biology",
    "anatomy": "biology",
    "physiology": "biology",

    # Economics
    "econ": "economics",
    "macro economics": "economics",
    "micro economics": "economics",
    "managerial economics": "economics",
    "business economics": "economics",

    # Everything below falls through to generic — listed here for documentation
    # AI/ML → generic (no dedicated profile; generic is designed to handle it)
    # "artificial intelligence": "generic",
    # "machine learning": "generic",
    # "deep learning": "generic",
    # "data science": "generic",
    # "natural language processing": "generic",
}


def _normalize_subject(subject: Optional[str]) -> str:
    """
    Normalize a raw subject string to a lowercase slug suitable for profile lookup.

    Examples:
        "Physics"                   → "physics"
        "Computer Science & Engg."  → "computer science  engg "
        "AI/ML"                     → "ai ml"
        None                        → ""
    """
    if not subject:
        return ""
    # Lower-case, replace punctuation/slashes with spaces, collapse whitespace
    slug = subject.strip().lower()
    slug = re.sub(r"[/\\&+,;]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    return slug


def _slug_to_filename(slug: str) -> str:
    """Convert a subject slug to a YAML filename slug (spaces → underscores)."""
    return slug.replace(" ", "_")


class SubjectProfileLoader:
    """
    Loads, validates, and caches SubjectProfile instances from YAML files.

    Profile resolution order:
        1. Check _SLUG_ALIASES for the normalized subject name.
        2. Try to load <normalized_slug>.yaml directly (spaces→underscores).
        3. Fall back to generic.yaml.

    The cache persists for the lifetime of the process (module-level singleton).
    """

    # Module-level cache: slug → SubjectProfile
    _cache: Dict[str, SubjectProfile] = {}
    _profiles_dir: Path = _PROFILES_DIR

    @classmethod
    def get(cls, subject: Optional[str]) -> SubjectProfile:
        """
        Resolve and return the SubjectProfile for the given subject name.

        Args:
            subject: Raw subject name from paper metadata (e.g. "Physics",
                     "AI and Machine Learning", "CSE 301"). May be None.

        Returns:
            A validated SubjectProfile. Never raises; falls back to generic.
        """
        normalized = _normalize_subject(subject)

        # 1. Check alias map
        resolved_slug = _SLUG_ALIASES.get(normalized)

        # 2. Try direct filename match if alias didn't resolve
        if not resolved_slug:
            file_slug = _slug_to_filename(normalized)
            candidate = cls._profiles_dir / f"{file_slug}.yaml"
            if candidate.is_file():
                resolved_slug = file_slug
            else:
                # Whole-word match: check if any alias key appears as a complete word
                # in the normalized name (prevents 'ec' matching 'subject')
                for alias_key, alias_slug in _SLUG_ALIASES.items():
                    # Build a word-boundary pattern for the alias key
                    pattern = r"(?<![a-z])" + re.escape(alias_key) + r"(?![a-z])"
                    if re.search(pattern, normalized):
                        resolved_slug = alias_slug
                        logger.debug(
                            f"SubjectProfileLoader: Word-boundary alias match "
                            f"'{alias_key}' in '{normalized}' → '{alias_slug}'"
                        )
                        break

        if not resolved_slug:
            logger.info(
                f"SubjectProfileLoader: No profile found for '{subject}' "
                f"(normalized='{normalized}'). Using generic fallback."
            )
            resolved_slug = _GENERIC_SLUG

        return cls._load_cached(resolved_slug)

    @classmethod
    def _load_cached(cls, slug: str) -> SubjectProfile:
        """Return cached profile or load from disk."""
        if slug in cls._cache:
            logger.debug(f"SubjectProfileLoader: Cache hit for '{slug}'")
            return cls._cache[slug]
        return cls._load_from_disk(slug)

    @classmethod
    def _load_from_disk(cls, slug: str) -> SubjectProfile:
        """
        Load and validate a YAML profile from disk.

        On any failure (file not found, YAML parse error, Pydantic validation error),
        loads generic.yaml instead. If generic.yaml also fails, raises RuntimeError.
        """
        profile_path = cls._profiles_dir / f"{slug}.yaml"

        try:
            raw = profile_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            if not isinstance(data, dict):
                raise ValueError(f"YAML root must be a mapping, got {type(data).__name__}")
            profile = SubjectProfile(**data)
            cls._cache[slug] = profile
            logger.info(f"SubjectProfileLoader: Loaded and cached profile '{slug}' from {profile_path}")
            return profile

        except FileNotFoundError:
            if slug == _GENERIC_SLUG:
                raise RuntimeError(
                    f"CRITICAL: generic.yaml not found at {profile_path}. "
                    "The system cannot operate without the generic fallback profile."
                )
            logger.warning(
                f"SubjectProfileLoader: Profile '{slug}' not found at {profile_path}. "
                "Falling back to generic."
            )
            return cls._load_cached(_GENERIC_SLUG)

        except yaml.YAMLError as exc:
            logger.error(
                f"SubjectProfileLoader: YAML parse error in '{profile_path}': {exc}. "
                "Falling back to generic."
            )
            if slug == _GENERIC_SLUG:
                raise RuntimeError(f"CRITICAL: generic.yaml has YAML parse errors: {exc}")
            return cls._load_cached(_GENERIC_SLUG)

        except ValidationError as exc:
            logger.error(
                f"SubjectProfileLoader: Pydantic validation failed for '{profile_path}': {exc}. "
                "Falling back to generic."
            )
            if slug == _GENERIC_SLUG:
                raise RuntimeError(
                    f"CRITICAL: generic.yaml fails Pydantic validation: {exc}"
                )
            return cls._load_cached(_GENERIC_SLUG)

    @classmethod
    def list_available_subjects(cls) -> list[str]:
        """Return a sorted list of all subject slugs available as YAML profiles."""
        return sorted(
            p.stem for p in cls._profiles_dir.glob("*.yaml")
        )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the in-memory cache (useful for testing or hot-reload)."""
        cls._cache.clear()
        logger.debug("SubjectProfileLoader: Cache cleared.")
