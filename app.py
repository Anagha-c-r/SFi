"""A stand-in for CBK's GDI API, for local development and demos.

Run:  uvicorn app.mock_cbk.app:app --port 9000
Then point the portal at it:
  CBK_TOKEN_URL=http://localhost:9000/oauth2/v1/token
  CBK_UAT_BASE=http://localhost:9000/preprod

Accepts client ID "demo-client" with secret "demo-secret". Behaves like the
guide describes: 200 with Status/RequestNo, 400 BadStructure when the dataset
array is missing, 400 MaximumSizeExceeded above MOCK_MAX_ROWS rows.
"""
from __future__ import annotations

import base64
import itertools
import os
import secrets
import time

from fastapi import FastAPI, Form, Header, Request
from fastapi.responses import JSONResponse

from app.datasets.registry import all_datasets

app = FastAPI(title="Mock CBK GDI API")
CLIENTS = {os.getenv("MOCK_CLIENT_ID", "demo-client"): os.getenv("MOCK_CLIENT_SECRET", "demo-secret")}
MAX_ROWS = int(os.getenv("MOCK_MAX_ROWS", "10000"))
_tokens: dict[str, float] = {}
_seq = itertools.count(47202012)
received: list[dict] = []  # inspected by tests
ENDPOINTS: dict[str, set[str]] = {}
for _d in all_datasets().values():  # some datasets share an endpoint in the guide
    ENDPOINTS.setdefault(_d.endpoint, set()).add(_d.array_key)


@app.post("/oauth2/v1/token")
async def token(authorization: str = Header(""), grant_type: str = Form(""), scope: str | None = Form(None)):
    if grant_type != "client_credentials":
        return JSONResponse({"error": "unsupported_grant_type"}, 400)
    try:
        cid, secret = base64.b64decode(authorization.removeprefix("Basic ")).decode().split(":", 1)
    except Exception:
        return JSONResponse({"error": "invalid_request", "error_description": "Missing Basic authorization"}, 400)
    if CLIENTS.get(cid) != secret:
        return JSONResponse({"error": "invalid_client", "error_description": "Unknown client"}, 400)
    tok = secrets.token_urlsafe(24)
    _tokens[tok] = time.time() + 3600
    return {"access_token": tok, "token_type": "Bearer", "expires_in": 3600}


@app.post("/preprod/api/v1/flows/rest/{api}/1.0/{operation}")
async def submit(api: str, operation: str, request: Request, authorization: str = Header("")):
    tok = authorization.removeprefix("Bearer ")
    if _tokens.get(tok, 0) < time.time():
        return JSONResponse({"error": "Unauthorized"}, 401)
    endpoint = f"/api/v1/flows/rest/{api}/1.0/{operation}"
    array_keys = ENDPOINTS.get(endpoint)
    if array_keys is None:
        return JSONResponse({"error": "Not Found"}, 404)
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        body = await request.json()
        rows = next((body[k] for k in array_keys if k in body), None)
        if not isinstance(rows, list) or body.get("IS_ATTACHED") != "N":
            return JSONResponse({"error": "BadStructure"}, 400)
        count = len(rows)
    else:
        form = await request.form()
        body = {k: v for k, v in form.items() if isinstance(v, str)}
        upload = next((v for v in form.values() if not isinstance(v, str)), None)
        if upload is None or body.get("IS_ATTACHED") != "Y":
            return JSONResponse({"error": "BadStructure"}, 400)
        count = max(0, (await upload.read()).decode().count("\n") - 1)
    if count > MAX_ROWS:
        return JSONResponse({"error": "MaximumSizeExceeded", "limit": MAX_ROWS}, 400)
    request_no = str(next(_seq))
    received.append({"endpoint": endpoint, "rows": count, "request_no": request_no, "envelope": {
        k: v for k, v in body.items() if not isinstance(v, list)}})
    return {"Status": "Successfully Submitted", "RequestNo": request_no}
