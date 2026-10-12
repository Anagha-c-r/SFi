"""Build the request CBK expects: a JSON envelope, or the same rows as a CSV file."""
from __future__ import annotations

import csv
import io
from datetime import date

from app.datasets.registry import DatasetDef


def envelope(
    dataset: DatasetDef,
    *,
    institution_code: str,
    reporting_date: date,
    rows: list[dict[str, str]],
    override_request_id: str | None = None,
    attached: bool = False,
    date_format: str = "%d-%b-%Y",
) -> dict:
    """The top-level JSON object from the guide's 'Sample Request Payload'."""
    return {
        "INSTITUTION_CODE": institution_code,
        "REQUEST_ID": override_request_id or "",
        "IS_ATTACHED": "Y" if attached else "N",
        "REPORTING_DATE": reporting_date.strftime(date_format),
        dataset.array_key: [] if attached else rows,
    }


def rows_to_csv(dataset: DatasetDef, rows: list[dict[str, str]]) -> bytes:
    columns = [f.payload_key for f in dataset.fields]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(columns)
    for r in rows:
        writer.writerow([r.get(c, "") for c in columns])
    return buf.getvalue().encode("utf-8")


def template_csv(dataset: DatasetDef) -> bytes:
    """A blank upload template: the field names plus one example row."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([f.name for f in dataset.fields])
    writer.writerow([f.example for f in dataset.fields])
    return buf.getvalue().encode("utf-8")
