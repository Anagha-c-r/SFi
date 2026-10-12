from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import db as dbmod
from app.api import admin, auth, dashboard, datasets, institution, submissions
from app.config import settings
from app.datasets.registry import all_datasets
from app.models import Institution, Role, Status, Submission, User
from app.security import hash_password

log = logging.getLogger("gdi")


def bootstrap() -> None:
    """Create tables and the first platform admin. Use Alembic for schema changes once live."""
    dbmod.Base.metadata.create_all(dbmod.engine)
    with dbmod.SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is None:
            password = settings.bootstrap_admin_password
            if not password:
                log.warning("No users exist and BOOTSTRAP_ADMIN_PASSWORD is not set; skipping admin creation.")
                return
            db.add(User(email=settings.bootstrap_admin_email.lower(), full_name="Platform Admin",
                        role=Role.platform_admin.value, password_hash=hash_password(password)))
            db.commit()
            log.info("Created platform admin %s", settings.bootstrap_admin_email)
        # stuck sends from a previous crash go back to the queue for a manual retry
        for sub in db.scalars(select(Submission).where(Submission.status == Status.sending.value)):
            sub.status = Status.failed.value
            sub.last_error = "The server restarted while this was being sent. Retry it."
        db.commit()
        if settings.seed_demo_data:
            from app.seed import seed_demo
            seed_demo(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    all_datasets()  # fail fast if a dataset file is broken
    bootstrap()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan,
              docs_url=None if settings.is_production else "/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, datasets.router, submissions.router, dashboard.router, institution.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "datasets": len(all_datasets())}
