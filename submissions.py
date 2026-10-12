from __future__ import annotations

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.datasets.registry import get_dataset
from app.db import get_db
from app.deps import current_institution, current_user, require
from app.models import AuditEvent, Institution, Role, Status, Submission, User
from app.schemas import OutcomeIn, Page, RejectIn, SubmissionDetail, SubmissionOut
from app.services import audit
from app.services import submissions as svc
from app.services.parsing import ParseError
from app.services.payload import rows_to_csv

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PREVIEW_ROWS = 50
MAKERS = (Role.admin, Role.maker)
CHECKERS = (Role.admin, Role.checker)


def to_out(sub: Submission, model=SubmissionOut, **extra):
    ds = get_dataset(sub.dataset_code)
    data = {c: getattr(sub, c) for c in SubmissionOut.model_fields if hasattr(sub, c)}
    data.update(
        dataset_title=ds.title if ds else sub.dataset_code,
        created_by_name=sub.created_by.full_name if sub.created_by else "",
        approved_by_name=sub.approved_by.full_name if sub.approved_by else None,
        **extra,
    )
    return model(**data)


def _get(db: Session, sub_id: str, institution: Institution) -> Submission:
    sub = db.get(Submission, sub_id)
    if sub is None or sub.institution_id != institution.id:
        raise HTTPException(404, "Submission not found.")
    return sub


def _transition(fn, *args):
    try:
        fn(*args)
    except svc.TransitionError as exc:
        raise HTTPException(409, str(exc))


@router.post("", response_model=SubmissionOut, status_code=201)
def upload(  # sync: parsing large files runs in the threadpool, not the event loop
    dataset_code: str = Form(...),
    reporting_date: date = Form(...),
    file: UploadFile = File(...),
    override_request_id: str | None = Form(None),
    transport: str | None = Form(None),
    user: User = Depends(require(*MAKERS)),
    institution: Institution = Depends(current_institution),
    db: Session = Depends(get_db),
):
    dataset = get_dataset(dataset_code)
    if dataset is None:
        raise HTTPException(404, "Dataset not found.")
    if transport not in (None, "", "json", "csv"):
        raise HTTPException(422, "transport must be 'json' or 'csv'.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 50 MB. Split it into smaller files.")
    try:
        sub = svc.create_from_upload(db, user=user, institution=institution, dataset=dataset,
                                     reporting_date=reporting_date, filename=file.filename or "upload.csv",
                                     data=data, override_request_id=override_request_id, transport=transport or None)
    except ParseError as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    return to_out(sub)


@router.get("", response_model=Page)
def list_submissions(
    status: str | None = None,
    dataset: str | None = None,
    q: str | None = Query(None, description="Search request number or filename"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(current_user),
    institution: Institution = Depends(current_institution),
    db: Session = Depends(get_db),
):
    stmt = select(Submission).where(Submission.institution_id == institution.id)
    if status:
        stmt = stmt.where(Submission.status.in_(status.split(",")))
    if dataset:
        stmt = stmt.where(Submission.dataset_code == dataset)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Submission.cbk_request_no.ilike(like) | Submission.original_filename.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Submission.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[to_out(s) for s in rows], total=total, page=page, page_size=page_size)


@router.get("/{sub_id}", response_model=SubmissionDetail)
def detail(sub_id: str, user: User = Depends(current_user), institution: Institution = Depends(current_institution),
           db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_type == "submission", AuditEvent.entity_id == sub.id)
                        .order_by(AuditEvent.created_at)).all()
    return to_out(
        sub, SubmissionDetail,
        issues=sub.issues[:1000], column_map=sub.column_map, cbk_response=sub.cbk_response,
        preview_rows=sub.rows[:PREVIEW_ROWS],
        events=[{"action": e.action, "at": e.created_at, "by": e.user.full_name if e.user else "System",
                 "detail": e.detail} for e in events],
    )


@router.post("/{sub_id}/request-approval", response_model=SubmissionOut)
def request_approval(sub_id: str, user: User = Depends(require(*MAKERS)),
                     institution: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    _transition(svc.request_approval, db, sub, user)
    db.commit()
    return to_out(sub)


@router.post("/{sub_id}/approve", response_model=SubmissionOut)
def approve(sub_id: str, background: BackgroundTasks, user: User = Depends(require(*CHECKERS)),
            institution: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    _transition(svc.approve, db, sub, user, institution)
    db.commit()
    background.add_task(svc.send, sub.id)
    return to_out(sub)


@router.post("/{sub_id}/reject", response_model=SubmissionOut)
def reject(sub_id: str, body: RejectIn, user: User = Depends(require(*CHECKERS)),
           institution: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    _transition(svc.reject, db, sub, user, body.note)
    db.commit()
    return to_out(sub)


@router.post("/{sub_id}/retry", response_model=SubmissionOut)
def retry(sub_id: str, background: BackgroundTasks, user: User = Depends(require(*CHECKERS)),
          institution: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    _transition(svc.retry, db, sub, user)
    db.commit()
    background.add_task(svc.send, sub.id)
    return to_out(sub)


@router.post("/{sub_id}/outcome", response_model=SubmissionOut)
def outcome(sub_id: str, body: OutcomeIn, user: User = Depends(require(Role.admin, Role.maker, Role.checker)),
            institution: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    _transition(svc.record_cbk_outcome, db, sub, user, body.accepted, body.note)
    db.commit()
    return to_out(sub)


@router.delete("/{sub_id}", status_code=204)
def delete(sub_id: str, user: User = Depends(require(*MAKERS)), institution: Institution = Depends(current_institution),
           db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    if sub.status not in {Status.invalid.value, Status.validated.value, Status.rejected.value}:
        raise HTTPException(409, "Only submissions that were never sent for approval or were rejected can be deleted.")
    audit.record(db, user=user, action="submission.deleted", entity_type="submission", entity_id=sub.id,
                 dataset=sub.dataset_code)
    db.delete(sub)
    db.commit()


# --- downloads ----------------------------------------------------------------
def _download(content: bytes, filename: str, media: str) -> Response:
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{sub_id}/payload.json")
def payload_json(sub_id: str, user: User = Depends(current_user), institution: Institution = Depends(current_institution),
                 db: Session = Depends(get_db)):
    """Exactly what is (or would be) sent to CBK."""
    sub = _get(db, sub_id, institution)
    try:
        dataset, env, _ = svc.build_request(sub, institution)
    except svc.TransitionError as exc:
        raise HTTPException(409, str(exc))
    body = {"endpoint": dataset.endpoint, "transport": sub.transport, "body": env}
    return _download(json.dumps(body, indent=2).encode(), f"{sub.dataset_code}_{sub.id[:8]}_payload.json", "application/json")


@router.get("/{sub_id}/data.csv")
def data_csv(sub_id: str, user: User = Depends(current_user), institution: Institution = Depends(current_institution),
             db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    dataset = get_dataset(sub.dataset_code)
    if dataset is None:
        raise HTTPException(409, f"Unknown dataset '{sub.dataset_code}'.")
    return _download(rows_to_csv(dataset, sub.rows), f"{sub.dataset_code}_{sub.id[:8]}.csv", "text/csv")


@router.get("/{sub_id}/issues.csv")
def issues_csv(sub_id: str, user: User = Depends(current_user), institution: Institution = Depends(current_institution),
               db: Session = Depends(get_db)):
    sub = _get(db, sub_id, institution)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Level", "Row", "Field", "Value", "Message"])
    for i in sub.issues:
        w.writerow([i.get("level"), i.get("row") or "", i.get("field") or "", i.get("value") or "", i.get("message")])
    return _download(buf.getvalue().encode(), f"{sub.dataset_code}_{sub.id[:8]}_issues.csv", "text/csv")
