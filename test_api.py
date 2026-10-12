"""End-to-end API tests: onboarding, upload, validation, maker-checker, sending to the mock CBK.

Run with: pytest
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.datasets.registry import get_dataset
from app.main import app
from app.mock_cbk import app as mock
from app.services import submissions as svc
from app.api import institution as inst_api

PASSWORD = "Strong-Pass-2026"


def mock_client_for(institution):
    return svc.CBKClient(client_id=institution.cbk_client_id, client_secret=svc.decrypt_secret(institution.cbk_client_secret_enc),
                         scope=None, environment=institution.environment,
                         transport=httpx.ASGITransport(app=mock.app))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def use_mock_cbk(monkeypatch):
    monkeypatch.setattr(svc, "client_for", mock_client_for)
    monkeypatch.setattr(inst_api, "client_for", mock_client_for)


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def bank(client):
    root = login(client, "root@finoworks.com", "Root-Pass-2026")
    r = client.post("/api/admin/institutions", headers=root, json={
        "name": "Test Bank", "institution_code": "0000009", "environment": "uat",
        "admin_email": "admin@testbank.ke", "admin_full_name": "Ada Admin", "admin_password": PASSWORD})
    assert r.status_code == 201, r.text
    admin = login(client, "admin@testbank.ke", PASSWORD)
    for email, role in [("maker@testbank.ke", "maker"), ("checker@testbank.ke", "checker"), ("viewer@testbank.ke", "viewer")]:
        r = client.post("/api/institution/users", headers=admin,
                        json={"email": email, "full_name": role.title(), "role": role, "password": PASSWORD})
        assert r.status_code == 201, r.text
    return {
        "admin": admin,
        "maker": login(client, "maker@testbank.ke", PASSWORD),
        "checker": login(client, "checker@testbank.ke", PASSWORD),
        "viewer": login(client, "viewer@testbank.ke", PASSWORD),
    }


def csv_for(code, rows=2, **override):
    ds = get_dataset(code)
    header = ",".join(f'"{f.name}"' for f in ds.fields)
    lines = [header]
    for i in range(1, rows + 1):
        vals = []
        for f in ds.fields:
            v = override.get(f.name, f.example)
            if f.name == "ROW ID":
                v = str(i)
            vals.append(f'"{v}"')
        lines.append(",".join(vals))
    return ("\n".join(lines) + "\n").encode()


def upload(client, headers, code="card_acquiring_transactions_information", data=None, **form):
    return client.post("/api/submissions", headers=headers,
                       data={"dataset_code": code, "reporting_date": "2026-09-30", **form},
                       files={"file": ("data.csv", data or csv_for(code), "text/csv")})


def test_health_and_datasets(client, bank):
    assert client.get("/api/health").json()["datasets"] == 46
    r = client.get("/api/datasets", headers=bank["viewer"])
    assert len(r.json()) == 46
    r = client.get("/api/datasets/foreign_exchange_positions_information/template.csv", headers=bank["viewer"])
    assert r.status_code == 200 and r.text.startswith("ROW ID")


def test_requires_login(client):
    assert client.get("/api/datasets").status_code == 401


def test_bad_password_rejected(client, bank):
    r = client.post("/api/auth/login", json={"email": "maker@testbank.ke", "password": "nope"})
    assert r.status_code == 401


def test_viewer_cannot_upload(client, bank):
    assert upload(client, bank["viewer"]).status_code == 403


def test_invalid_upload_is_flagged(client, bank):
    data = csv_for("card_acquiring_transactions_information", **{"VALUE OF TRANSACTIONS": "lots"})
    r = upload(client, bank["maker"], data=data)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "invalid" and body["error_count"] == 2
    detail = client.get(f"/api/submissions/{body['id']}", headers=bank["maker"]).json()
    assert detail["issues"][0]["field"] == "VALUE OF TRANSACTIONS"
    # invalid submissions can't go for approval
    r = client.post(f"/api/submissions/{body['id']}/request-approval", headers=bank["maker"])
    assert r.status_code == 409


def test_full_flow_to_cbk(client, bank):
    # credentials are needed before approval
    r = client.put("/api/institution/settings", headers=bank["admin"],
                   json={"cbk_client_id": "demo-client", "cbk_client_secret": "demo-secret"})
    assert r.status_code == 200 and r.json()["has_credentials"] is True
    assert "cbk_client_secret" not in r.json()
    r = client.post("/api/institution/test-connection", headers=bank["admin"])
    assert r.json()["ok"] is True, r.json()

    sub = upload(client, bank["maker"]).json()
    assert sub["status"] == "validated", sub
    sid = sub["id"]
    assert client.post(f"/api/submissions/{sid}/request-approval", headers=bank["maker"]).json()["status"] == "pending_approval"
    # maker can't approve (role), and four-eyes applies to admins too
    assert client.post(f"/api/submissions/{sid}/approve", headers=bank["maker"]).status_code == 403

    r = client.post(f"/api/submissions/{sid}/approve", headers=bank["checker"])
    assert r.status_code == 200, r.text
    final = client.get(f"/api/submissions/{sid}", headers=bank["checker"]).json()
    assert final["status"] == "submitted", final
    assert final["cbk_request_no"]
    sent = mock.received[-1]
    assert sent["endpoint"].endswith("submitCardAcquiringTransInfo")
    assert sent["envelope"]["INSTITUTION_CODE"] == "0000009"
    assert sent["envelope"]["REPORTING_DATE"] == "30-Sep-2026"
    assert sent["rows"] == 2

    payload = client.get(f"/api/submissions/{sid}/payload.json", headers=bank["viewer"]).json()
    assert payload["body"]["CARDACQUIRINGTRANS_DATA"][0]["ROW ID"] == "1"

    r = client.post(f"/api/submissions/{sid}/outcome", headers=bank["checker"], json={"accepted": True})
    assert r.json()["status"] == "cbk_accepted"


def test_csv_transport_and_override(client, bank):
    sub = upload(client, bank["maker"], transport="csv", override_request_id="47202012").json()
    client.post(f"/api/submissions/{sub['id']}/request-approval", headers=bank["maker"])
    client.post(f"/api/submissions/{sub['id']}/approve", headers=bank["checker"])
    final = client.get(f"/api/submissions/{sub['id']}", headers=bank["checker"]).json()
    assert final["status"] == "submitted", final
    sent = mock.received[-1]
    assert sent["envelope"]["IS_ATTACHED"] == "Y"
    assert sent["envelope"]["REQUEST_ID"] == "47202012"
    assert sent["rows"] == 2


def test_cbk_failure_then_retry(client, bank, monkeypatch):
    monkeypatch.setattr(mock, "MAX_ROWS", 1)
    sub = upload(client, bank["maker"]).json()
    client.post(f"/api/submissions/{sub['id']}/request-approval", headers=bank["maker"])
    client.post(f"/api/submissions/{sub['id']}/approve", headers=bank["checker"])
    failed = client.get(f"/api/submissions/{sub['id']}", headers=bank["checker"]).json()
    assert failed["status"] == "failed"
    assert "MaximumSizeExceeded" in failed["last_error"]
    monkeypatch.setattr(mock, "MAX_ROWS", 10000)
    client.post(f"/api/submissions/{sub['id']}/retry", headers=bank["checker"])
    assert client.get(f"/api/submissions/{sub['id']}", headers=bank["checker"]).json()["status"] == "submitted"


def test_tenants_are_isolated(client, bank):
    root = login(client, "root@finoworks.com", "Root-Pass-2026")
    client.post("/api/admin/institutions", headers=root, json={
        "name": "Other Bank", "institution_code": "0000010", "admin_email": "admin@other.ke",
        "admin_full_name": "Other", "admin_password": PASSWORD})
    other = login(client, "admin@other.ke", PASSWORD)
    mine = client.get("/api/submissions", headers=bank["maker"]).json()
    assert mine["total"] > 0
    sid = mine["items"][0]["id"]
    assert client.get(f"/api/submissions/{sid}", headers=other).status_code == 404
    assert client.get("/api/submissions", headers=other).json()["total"] == 0


def test_dashboard_and_audit(client, bank):
    d = client.get("/api/dashboard", headers=bank["viewer"]).json()
    assert d["totals"]["sent"] >= 2
    assert len(d["activity"]) == 30 and len(d["coverage"]) == 46
    log = client.get("/api/institution/audit", headers=bank["admin"]).json()
    actions = {e["action"] for e in log["items"]}
    assert {"submission.uploaded", "submission.approved", "submission.sent"} <= actions
