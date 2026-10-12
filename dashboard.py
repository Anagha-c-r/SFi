from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.datasets.registry import all_datasets
from app.db import get_db
from app.deps import current_institution, current_user
from app.models import Institution, Status, Submission, User
from app.api.submissions import to_out

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: User = Depends(current_user), institution: Institution = Depends(current_institution),
              db: Session = Depends(get_db)):
    base = select(Submission).where(Submission.institution_id == institution.id)
    by_status = dict(db.execute(
        select(Submission.status, func.count()).where(Submission.institution_id == institution.id)
        .group_by(Submission.status)).all())

    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent_rows = db.execute(
        select(Submission.created_at, Submission.status)
        .where(Submission.institution_id == institution.id, Submission.created_at >= since)).all()
    daily: dict[str, dict[str, int]] = {}
    for created, st in recent_rows:
        day = created.date().isoformat()
        bucket = daily.setdefault(day, {"sent": 0, "failed": 0, "other": 0})
        if st in (Status.submitted.value, Status.cbk_accepted.value, Status.cbk_rejected.value):
            bucket["sent"] += 1
        elif st in (Status.failed.value, Status.invalid.value):
            bucket["failed"] += 1
        else:
            bucket["other"] += 1
    today = datetime.now(timezone.utc).date()
    activity = [{"date": (today - timedelta(days=i)).isoformat(), **daily.get((today - timedelta(days=i)).isoformat(),
                 {"sent": 0, "failed": 0, "other": 0})} for i in range(29, -1, -1)]

    last_by_dataset = dict(db.execute(
        select(Submission.dataset_code, func.max(Submission.submitted_at))
        .where(Submission.institution_id == institution.id, Submission.submitted_at.is_not(None))
        .group_by(Submission.dataset_code)).all())
    coverage = [{**d.to_summary(), "last_submitted_at": last_by_dataset.get(d.code)} for d in all_datasets().values()]

    attention = db.scalars(base.where(Submission.status.in_(
        [Status.pending_approval.value, Status.failed.value, Status.invalid.value]))
        .order_by(Submission.updated_at.desc()).limit(8)).all()
    recent = db.scalars(base.order_by(Submission.created_at.desc()).limit(8)).all()

    sent_total = sum(by_status.get(s.value, 0) for s in (Status.submitted, Status.cbk_accepted, Status.cbk_rejected))
    return {
        "institution": {"name": institution.name, "code": institution.institution_code,
                        "environment": institution.environment, "has_credentials": institution.has_credentials},
        "totals": {
            "sent": sent_total,
            "pending_approval": by_status.get(Status.pending_approval.value, 0),
            "failed": by_status.get(Status.failed.value, 0),
            "invalid": by_status.get(Status.invalid.value, 0),
            "in_flight": by_status.get(Status.queued.value, 0) + by_status.get(Status.sending.value, 0),
            "datasets_reported": len(last_by_dataset),
            "datasets_total": len(coverage),
        },
        "by_status": by_status,
        "activity": activity,
        "coverage": coverage,
        "attention": [to_out(s) for s in attention],
        "recent": [to_out(s) for s in recent],
    }
