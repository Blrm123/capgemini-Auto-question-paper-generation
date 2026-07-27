"""
rag/src/ingestion/image_registry.py

Image Registry for the Agentic Question Paper Generator.

Responsibilities:
  - Track every extracted/rendered image with full metadata
  - Provide a validated set of academic image IDs to agents
  - Persist registry to uploaded_documents/image_registry.json
  - Prevent LLM from hallucinating image paths by supplying an explicit allowlist
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ImageRecord:
    image_id: str
    source_file: str
    page_num: int
    width: int
    height: int
    file_path: str
    relative_path: str
    extraction_method: str
    quality_score: float
    is_academic: bool
    caption: str
    filter_reason: str


class ImageRegistry:
    REGISTRY_FILENAME = "image_registry.json"

    def __init__(self, base_dir):
        self._base_dir = base_dir
        self._records = {}
        self._registry_path = base_dir / "uploaded_documents" / self.REGISTRY_FILENAME

    def register(self, record):
        self._records[record.image_id] = record

    def clear_for_source(self, source_file):
        stem = Path(source_file).stem
        to_delete = [img_id for img_id, rec in self._records.items()
                     if rec.source_file == stem or rec.source_file == source_file]
        for img_id in to_delete:
            del self._records[img_id]

    def get(self, image_id):
        return self._records.get(image_id)

    def get_academic_ids(self):
        return [img_id for img_id, rec in self._records.items() if rec.is_academic]

    def get_academic_records(self):
        return [rec for rec in self._records.values() if rec.is_academic]

    def is_valid_image_id(self, image_id):
        rec = self._records.get(image_id)
        return rec is not None and rec.is_academic

    def get_relative_path(self, image_id):
        rec = self._records.get(image_id)
        return rec.relative_path if rec else None

    def summary(self):
        total = len(self._records)
        academic = len(self.get_academic_ids())
        return f"Registry: {total} total images, {academic} academic (usable)"

    def save(self):
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {img_id: asdict(rec) for img_id, rec in self._records.items()}
        with open(self._registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self):
        if not self._registry_path.is_file():
            return
        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._records = {}
            for img_id, d in data.items():
                self._records[img_id] = ImageRecord(**d)
        except Exception:
            self._records = {}

    def to_prompt_list(self):
        ids = self.get_academic_ids()
        if not ids:
            return "(none)"
        return ", ".join(ids)


def make_image_id(file_stem, page_num, idx, method="r"):
    safe_stem = re.sub(r"[^a-zA-Z0-9\-_]", "-", file_stem)[:40]
    return f"{safe_stem}_p{page_num}_{method}{idx}"
