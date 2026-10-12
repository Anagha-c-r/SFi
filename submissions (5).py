"""Submission lifecycle: upload -> validate -> approve -> send to CBK."""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.datasets.registry import DatasetDef, get_dataset
from app import db as dbmod
from app.models import Institution, Status, Submission, User, utcnow
from app.security import decrypt_secret
from app.services import audit
from app.services.cbk_client import CBKClient, CBKError
from app.services.parsing import parse_upload
from app.services.payload import envelope, rows_to_csv
from app.services.validation import validate_rows

log = logging.getLogger(__name__)


class TransitionError(ValueError):
    pass


def create_from_upload(db: Session, *, user: User, institution: Institution, dataset: DatasetDef,
                       reporting_date: date, filename: str, data: bytes,
                       override_request_id: str | None, transport: str | None) -> Submission:
    parsed = parse_upload(filename, data)  # raises ParseError
    result = validate_rows(dataset, parsed.headers, parsed.rows, date_format=institution.date_format)
    chosen = transport or ("csv" if len(result.rows) > settings.json_row_limit else "json")
    sub = Submission(
        institution_id=institution.id,
        dataset_code=dataset.code,
        reporting_date=reporting_date,
        status=Status.validated.value if result.is_valid else Status.invalid.value,
        original_filename=filename,
        row_count=len(result.rows),
        error_count=result.error_count,
        warning_count=result.warning_count,
        rows=result.rows,
        issues=[i.as_dict() for i in result.issues],
        column_map=result.column_map,
        override_request_id=(override_request_id or "").strip() or None,
        transport=chosen,
        environment=institution.environment,
        created_by_id=user.id,
    )
    db.add(sub)
    db.flush()
    audit.record(db, user=user, action="submission.uploaded", entity_type="submission", entity_id=sub.id,
                 dataset=dataset.code, rows=sub.row_count, errors=sub.error_count, filename=filename)
    return sub


def _require(sub: Submission, *allowed: Status) -> None:
    if sub.status not in {s.value for s in allowed}:
        raise TransitionError(f"This action is not allowed while the submission is '{sub.status}'.")


def request_approval(db: Session, sub: Submission, user: User) -> None:
    _require(sub, Status.validated, Status.rejected)
    sub.status = Status.pending_approval.value
    sub.review_note = None
    audit.record(db, user=user, action="submission.approval_requested", entity_type="submission", entity_id=sub.id)


def approve(db: Session, sub: Submission, user: User, institution: Institution) -> None:
    _require(sub, Status.pending_approval)
    if institution.four_eyes and sub.created_by_id == user.id:
        raise TransitionError("Four-eyes check: someone other than the uploader must approve this submission.")
    if not institution.has_credentials:
        raise TransitionError("Add your CBK client ID and secret in Settings before sending data to CBK.")
    sub.status = Status.queued.value
    sub.approved_by_id = user.id
    audit.record(db, user=user, action="submission.approved", entity_type="submission", entity_id=sub.id)


def reject(db: Session, sub: Submission, user: User, note: str) -> None:
    _require(sub, Status.pending_approval)
    sub.status = Status.rejected.value
    sub.review_note = note
    audit.record(db, user=user, action="submission.rejected", entity_type="submission", entity_id=sub.id, note=note)


def retry(db: Session, sub: Submission, user: User) -> None:
    _require(sub, Status.failed)
    sub.status = Status.queued.value
    audit.record(db, user=user, action="submission.retry", entity_type="submission", entity_id=sub.id)


def record_cbk_outcome(db: Session, sub: Submission, user: User, accepted: bool, note: str | None) -> None:
    _require(sub, Status.submitted, Status.cbk_accepted, Status.cbk_rejected)
    sub.status = (Status.cbk_accepted if accepted else Status.cbk_rejected).value
    if note:
        sub.review_note = note
    audit.record(db, user=user, action="submission.cbk_outcome", entity_type="submission", entity_id=sub.id,
                 accepted=accepted, note=note)


def build_request(sub: Submission, institution: Institution) -> tuple[DatasetDef, dict, bytes | None]:
    dataset = get_dataset(sub.dataset_code)
    if dataset is None:
        raise TransitionError(f"Unknown dataset '{sub.dataset_code}'.")
    attached = sub.transport == "csv"
    env = envelope(dataset, institution_code=institution.institution_code, reporting_date=sub.reporting_date,
                   rows=sub.rows, override_request_id=sub.override_request_id, attached=attached,
                   date_format=institution.date_format)
    return dataset, env, rows_to_csv(dataset, sub.rows) if attached else None


def client_for(institution: Institution, **kw) -> CBKClient:
    return CBKClient(client_id=institution.cbk_client_id or "",
                     client_secret=decrypt_secret(institution.cbk_client_secret_enc or ""),
                     scope=institution.cbk_scope, environment=institution.environment, **kw)


async def send(submission_id: str, *, client_factory=None) -> None:
    """Send one queued submission to CBK. Runs as a background task with its own DB session."""
    db = dbmod.SessionLocal()
    try:
        sub = db.get(Submission, submission_id)
        if sub is None or sub.status != Status.queued.value:
            return
        institution = db.get(Institution, sub.institution_id)
        sub.status = Status.sending.value
        sub.attempts += 1
        db.commit()
        try:
            dataset, env, csv_bytes = build_request(sub, institution)
            factory = client_factory or globals()["client_for"]
            result = await factory(institution).submit(
                dataset.endpoint, envelope=env, csv_bytes=csv_bytes,
                csv_filename=f"{dataset.code}_{sub.reporting_date:%Y%m%d}.csv")
            sub.status = Status.submitted.value
            sub.cbk_http_status = result.http_status
            sub.cbk_status_text = result.status_text
            sub.cbk_request_no = result.request_no
            sub.cbk_response = result.body if isinstance(result.body, dict) else {"raw": result.body}
            sub.last_error = None
            sub.submitted_at = utcnow()
            audit.record(db, user=None, institution_id=sub.institution_id, action="submission.sent",
                         entity_type="submission", entity_id=sub.id, request_no=result.request_no)
        except (CBKError, TransitionError, RuntimeError) as exc:
            sub.status = Status.failed.value
            sub.last_error = str(exc)
            sub.cbk_http_status = getattr(exc, "http_status", None)
            body = getattr(exc, "body", None)
            sub.cbk_response = body if isinstance(body, dict) else ({"raw": body} if body else None)
            audit.record(db, user=None, institution_id=sub.institution_id, action="submission.send_failed",
                         entity_type="submission", entity_id=sub.id, error=str(exc))
        db.commit()
    except Exception:  # never let a background task die silently
        log.exception("Unexpected error sending submission %s", submission_id)
        db.rollback()
        sub = db.get(Submission, submission_id)
        if sub is not None:
            sub.status = Status.failed.value
            sub.last_error = "Unexpected server error while sending. See server logs."
            db.commit()
    finally:
        db.close()
