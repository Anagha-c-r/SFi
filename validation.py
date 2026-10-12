"""Validate uploaded rows against a dataset definition and normalize them.

What this checks (from the CBK GDI guide):
  * every required column is present and filled in
  * numbers are numbers (thousands separators are stripped)
  * dates are real dates; they are rewritten into one output format
  * ROW ID is unique, and is generated when the file has none

CBK's own business rules (code lists such as CDCH07, value ranges and
cross-field checks) live in Excel templates that are not part of the guide.
They can be added per field later as extra checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.datasets.registry import DatasetDef, FieldDef, normalize_header

DEFAULT_DATE_FORMAT = "%d-%b-%Y"  # 03-Jun-2020, the format the guide specifies

DATE_INPUT_FORMATS = (
    "%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y-%m-%d %H:%M:%S", "%Y%m%d",
)
MAX_ERRORS = 5000


@dataclass
class Issue:
    row: int | None  # 1-based data row, None for file-level issues
    field: str | None
    value: str | None
    message: str
    level: str = "error"  # "error" | "warning"

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ValidationResult:
    rows: list[dict[str, str]]  # keyed by CBK payload key, ready to send
    issues: list[Issue] = field(default_factory=list)
    column_map: dict[str, str] = field(default_factory=dict)  # upload header -> field key
    unknown_columns: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warning")

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0 and len(self.rows) > 0


def map_columns(dataset: DatasetDef, headers: list[str]) -> tuple[dict[str, FieldDef], list[str]]:
    """Match upload headers to dataset fields by name, payload key or snake key."""
    lookup: dict[str, FieldDef] = {}
    for f in dataset.fields:
        for alias in f.aliases():
            lookup.setdefault(alias, f)
    mapped, unknown, taken = {}, [], set()
    for h in headers:
        f = lookup.get(normalize_header(h))
        if f and f.key not in taken:
            mapped[h] = f
            taken.add(f.key)
        elif h.strip():
            unknown.append(h)
    return mapped, unknown


def parse_date(value: str, *, day_first: bool = True) -> date | None:
    v = value.strip()
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    if not day_first:
        try:
            return datetime.strptime(v, "%m/%d/%Y").date()
        except ValueError:
            pass
    return None


def parse_number(value: str) -> Decimal | None:
    v = value.strip().replace(",", "").replace(" ", "")
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
    try:
        d = Decimal(v)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def validate_rows(
    dataset: DatasetDef,
    headers: list[str],
    raw_rows: list[dict[str, str]],
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
    day_first: bool = True,
) -> ValidationResult:
    mapped, unknown = map_columns(dataset, headers)
    result = ValidationResult(rows=[], column_map={h: f.key for h, f in mapped.items()}, unknown_columns=unknown)
    present = {f.key for f in mapped.values()}
    row_id = dataset.row_id_field

    for h in unknown:
        result.issues.append(Issue(None, None, h, f"Column '{h}' is not part of {dataset.title} and will be ignored.", "warning"))
    for f in dataset.fields:
        if f.required and f.key not in present and f is not row_id:
            result.issues.append(Issue(None, f.name, None, f"Required column '{f.name}' is missing."))
    if not raw_rows:
        result.issues.append(Issue(None, None, None, "The file has no data rows."))
        return result

    header_for = {f.key: h for h, f in mapped.items()}
    seen_ids: dict[str, int] = {}

    for idx, raw in enumerate(raw_rows, start=1):
        out: dict[str, str] = {}
        for f in dataset.fields:
            h = header_for.get(f.key)
            value = (raw.get(h) or "").strip() if h else ""

            if f is row_id:
                value = value or str(idx)
                if value in seen_ids:
                    _add(result, Issue(idx, f.name, value, f"ROW ID {value} is also used on row {seen_ids[value]}."))
                seen_ids[value] = idx
                out[f.payload_key] = value
                continue

            if not value:
                if f.required and h:
                    _add(result, Issue(idx, f.name, value, "This field is required."))
                out[f.payload_key] = ""
                continue

            if f.type == "number":
                num = parse_number(value)
                if num is None:
                    _add(result, Issue(idx, f.name, value, "Must be a number."))
                    out[f.payload_key] = value
                else:
                    out[f.payload_key] = format(num, "f")
            elif f.type == "date":
                d = parse_date(value, day_first=day_first)
                if d is None:
                    _add(result, Issue(idx, f.name, value, "Not a recognised date. Use a format like 03-Jun-2020."))
                    out[f.payload_key] = value
                else:
                    out[f.payload_key] = d.strftime(date_format)
            else:
                out[f.payload_key] = value
        result.rows.append(out)
    return result


def _add(result: ValidationResult, issue: Issue) -> None:
    if len(result.issues) < MAX_ERRORS:
        result.issues.append(issue)
