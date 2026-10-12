# GDI Reporting Portal

A web portal for filing returns to the Central Bank of Kenya (CBK) through its **Granular Data Integration (GDI) API**. Finoworks hosts it, and each institution (banks, microfinance banks, CRBs, money remittance providers, forex bureaus) gets its own account.

Teams upload a CSV or Excel file and the portal checks it on the spot. An approver signs off, and the portal sends the data to CBK in the format the GDI guide specifies. Every step is logged.

## What it does

- **All 46 GDI datasets**, from card acquiring through forex transactions. Each is defined by a JSON file in `backend/app/datasets/`, generated from the CBK guide. Fixing a field is a config change, not code.
- **Upload and check.** CSV or `.xlsx`. Columns can use the guide's names, CBK's payload keys or snake_case. Numbers lose their thousands separators. Dates in any common format are rewritten into the format CBK wants. ROW IDs are generated when the file has none, and duplicates are flagged. Errors are listed per row and can be downloaded.
- **Maker-checker.** Preparers upload, approvers approve. With four-eyes on, which is the default, nobody can approve their own upload.
- **CBK integration.** OAuth 2.0 client-credentials login with token caching and automatic re-login. The data goes as a JSON payload, or as an attached CSV for large files. Earlier requests can be overridden with `REQUEST_ID`. Failed sends can be retried, and `BadStructure` and `MaximumSizeExceeded` come back as readable messages.
- **Multi-tenant.** Every query is scoped to the user's institution. Each institution has its own CBK credentials, encrypted at rest with Fernet, and its own environment, UAT or production. In production the whole UI turns red at the top.
- **Audit log.** Sign-ins, settings changes, uploads, approvals and CBK responses.
- **Mock CBK server** (`backend/app/mock_cbk`), which behaves like the guide describes, so you can build and demo without CBK credentials.

## Run it

You need Docker.

```bash
cp .env.example .env          # then set JWT_SECRET, ENCRYPTION_KEY, BOOTSTRAP_ADMIN_PASSWORD
docker compose up --build
```

Then open http://localhost:8080.

| Who | Email | Password |
|---|---|---|
| Finoworks platform admin | `admin@finoworks.com` | `BOOTSTRAP_ADMIN_PASSWORD` from `.env` |
| Demo bank administrator | `admin@demobank.example` | `Demo-Pass-2026` |
| Demo bank preparer | `maker@demobank.example` | `Demo-Pass-2026` |
| Demo bank approver | `checker@demobank.example` | `Demo-Pass-2026` |

The demo users exist only when `SEED_DEMO_DATA=true`. The demo bank is wired to the mock CBK, so the whole flow works end to end. To try it:

1. Sign in as the preparer.
2. Open **Datasets → Card Acquiring Transactions Information** and download the CSV template.
3. Upload the template with a reporting date, then click **Send for approval**.
4. Sign in as the approver and approve the submission. It shows **Sent to CBK** with a request number.

### Without Docker

```bash
# API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
BOOTSTRAP_ADMIN_PASSWORD=Change-Me-2026 SEED_DEMO_DATA=true \
CBK_TOKEN_URL=http://localhost:9000/oauth2/v1/token CBK_UAT_BASE=http://localhost:9000/preprod \
uvicorn app.main:app --reload            # SQLite by default; API docs at http://localhost:8000/api/docs
uvicorn app.mock_cbk.app:app --port 9000 # in a second terminal

# Web app
cd frontend
npm install
npm run dev                              # http://localhost:5173, proxies /api to :8000
```

### Tests

```bash
cd backend && pytest
```

- `test_core.py` checks all 46 dataset definitions, file parsing, validation and payload building.
- `test_api.py` runs the full flow against the mock CBK: onboarding, roles, invalid uploads, maker-checker, JSON and CSV sends, failure and retry, and tenant isolation.

## How it's built

```
backend/                FastAPI + SQLAlchemy 2 (Postgres in production, SQLite for tests)
  app/datasets/*.json   the 46 dataset definitions; registry.py loads them
  app/services/         parsing, validation, payload building, CBK client, submission lifecycle
  app/api/              HTTP routes: auth, datasets, submissions, dashboard, institution, admin
  app/mock_cbk/         stand-in for CBK's API
frontend/               React 18 + TypeScript + Vite, no UI framework
tools/                  scripts that extracted the dataset definitions from the CBK PDF
docs/CBK_GUIDE_ISSUES.md  problems in CBK's guide to clarify with CBK
```

A submission's statuses, in order:

`invalid` | `validated` → `pending_approval` → (`rejected`) → `queued` → `sending` → `submitted` | `failed` → `cbk_accepted` | `cbk_rejected`

CBK emails its validation result. Users record it on the submission until CBK offers a status API.

### Regenerating the dataset definitions

```bash
python tools/extract_schemas.py pages.json tools/raw_schemas   # pages.json: pdfplumber dump of the guide
python tools/finalize_schemas.py tools/raw_schemas backend/app/datasets
```

Manual corrections live in `OVERRIDES` in `tools/finalize_schemas.py`.

## Before going live

- [ ] Get answers from CBK on [docs/CBK_GUIDE_ISSUES.md](docs/CBK_GUIDE_ISSUES.md), especially the duplicated endpoints, the request format and the date format.
- [ ] Get CBK's Excel business-rule templates and add the code-list checks to validation.
- [ ] Test each dataset against CBK UAT with real credentials.
- [ ] Set strong `JWT_SECRET` and `ENCRYPTION_KEY` values, and keep `ENCRYPTION_KEY` backed up. Losing it means every institution has to re-enter its CBK secret.
- [ ] Add Alembic migrations. Tables are currently created on startup.
- [ ] Move sending to a worker queue (e.g. RQ or Celery) if files get large. Today it runs as a FastAPI background task.
- [ ] Add MFA and password-reset email. Move the login lockout to Redis when running more than one API process.
- [ ] Put it behind HTTPS and set `ENVIRONMENT=production`. That turns off `/api/docs` and makes `ENCRYPTION_KEY` mandatory.
