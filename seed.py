"""Demo data for local development (SEED_DEMO_DATA=true). Never enable in production."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Institution, Role, User
from app.security import encrypt_secret, hash_password

DEMO_PASSWORD = "Demo-Pass-2026"


def seed_demo(db: Session) -> None:
    if db.scalar(select(Institution).where(Institution.institution_code == "0000001")):
        return
    inst = Institution(name="Demo Commercial Bank", institution_code="0000001", category="commercial_bank",
                       environment="uat", cbk_client_id="demo-client", cbk_client_secret_enc=encrypt_secret("demo-secret"),
                       notification_email="reporting@demobank.example")
    db.add(inst)
    db.flush()
    for email, name, role in [
        ("admin@demobank.example", "Amina Otieno", Role.admin),
        ("maker@demobank.example", "Brian Kamau", Role.maker),
        ("checker@demobank.example", "Cynthia Wanjiru", Role.checker),
    ]:
        db.add(User(institution_id=inst.id, email=email, full_name=name, role=role.value,
                    password_hash=hash_password(DEMO_PASSWORD)))
    db.commit()
