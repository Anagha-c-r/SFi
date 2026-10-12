"""Loads the 46 CBK GDI dataset definitions from the JSON files in this folder.

Each JSON file describes one dataset: its CBK endpoint, the name of the array
that carries the rows, and the fields of each row. Fixing a dataset means
editing its JSON file; no code changes are needed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATASET_DIR = Path(__file__).parent


def normalize_header(value: str) -> str:
    """Normalize a column header so 'Row ID', 'ROW_ID' and 'row-id' all match."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


@dataclass(frozen=True)
class FieldDef:
    key: str
    name: str
    payload_key: str
    type: str  # "string" | "number" | "date"
    required: bool
    description: str = ""
    example: str = ""

    def aliases(self) -> set[str]:
        return {normalize_header(self.key), normalize_header(self.name), normalize_header(self.payload_key)}


@dataclass(frozen=True)
class DatasetDef:
    number: int
    code: str
    title: str
    group: str
    frequency: str
    endpoint: str
    array_key: str
    notes: str
    source_pages: tuple[int, int]
    fields: tuple[FieldDef, ...] = field(default_factory=tuple)

    @property
    def row_id_field(self) -> FieldDef | None:
        return next((f for f in self.fields if normalize_header(f.name) == "ROWID"), None)

    def to_summary(self) -> dict:
        return {
            "number": self.number,
            "code": self.code,
            "title": self.title,
            "group": self.group,
            "frequency": self.frequency,
            "field_count": len(self.fields),
            "notes": self.notes,
        }

    def to_detail(self) -> dict:
        return {
            **self.to_summary(),
            "endpoint": self.endpoint,
            "array_key": self.array_key,
            "source_pages": list(self.source_pages),
            "fields": [f.__dict__ for f in self.fields],
        }


def _load(path: Path) -> DatasetDef:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return DatasetDef(
        number=raw["number"],
        code=raw["code"],
        title=raw["title"],
        group=raw["group"],
        frequency=raw.get("frequency", "periodic"),
        endpoint=raw["endpoint"],
        array_key=raw["array_key"],
        notes=raw.get("notes", ""),
        source_pages=tuple(raw.get("source_pages", (0, 0))),
        fields=tuple(FieldDef(**f) for f in raw["fields"]),
    )


@lru_cache(maxsize=1)
def all_datasets() -> dict[str, DatasetDef]:
    items = [_load(p) for p in sorted(DATASET_DIR.glob("*.json"))]
    return {d.code: d for d in sorted(items, key=lambda d: d.number)}


def get_dataset(code: str) -> DatasetDef | None:
    return all_datasets().get(code)
