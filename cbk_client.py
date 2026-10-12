"""Client for CBK's GDI API: OAuth 2.0 client-credentials login and dataset submission.

Assumptions to confirm against CBK's curl samples (not included in the guide PDF):
  * JSON submissions are sent as an application/json body (the guide's sample payload).
  * CSV submissions are sent as multipart/form-data: the envelope fields as text
    parts plus the CSV as a file part named by CBK_FILE_FIELD (default "file").
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

import httpx

from app.config import settings

FILE_FIELD = os.getenv("CBK_FILE_FIELD", "file")


class CBKError(Exception):
    def __init__(self, message: str, *, http_status: int | None = None, body: object = None, retryable: bool = False):
        super().__init__(message)
        self.http_status = http_status
        self.body = body
        self.retryable = retryable


@dataclass
class SubmitResult:
    http_status: int
    status_text: str
    request_no: str | None
    body: object


@dataclass
class _Token:
    value: str
    expires_at: float


_tokens: dict[tuple[str, str], _Token] = {}
_lock = asyncio.Lock()


def base_url(environment: str) -> str:
    return settings.cbk_prod_base if environment == "prod" else settings.cbk_uat_base


def _body(resp: httpx.Response) -> object:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:4000]


class CBKClient:
    def __init__(self, *, client_id: str, client_secret: str, scope: str | None, environment: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.environment = environment
        self._transport = transport

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=settings.cbk_timeout_seconds, transport=self._transport)

    async def get_token(self, *, force: bool = False) -> str:
        key = (self.environment, self.client_id)
        async with _lock:
            tok = _tokens.get(key)
            if tok and not force and tok.expires_at - 60 > time.time():
                return tok.value
            data = {"grant_type": "client_credentials"}
            if self.scope:
                data["scope"] = self.scope
            async with self._http() as http:
                try:
                    resp = await http.post(settings.cbk_token_url, data=data, auth=(self.client_id, self.client_secret))
                except httpx.HTTPError as exc:
                    raise CBKError(f"Could not reach the CBK identity service: {exc}", retryable=True) from exc
            body = _body(resp)
            if resp.status_code != 200 or not isinstance(body, dict) or "access_token" not in body:
                desc = body.get("error_description") or body.get("error") if isinstance(body, dict) else body
                raise CBKError(f"CBK login failed ({resp.status_code}): {desc}", http_status=resp.status_code, body=body)
            _tokens[key] = _Token(body["access_token"], time.time() + float(body.get("expires_in", 3600)))
            return body["access_token"]

    async def submit(self, endpoint: str, *, envelope: dict, csv_bytes: bytes | None = None,
                     csv_filename: str = "data.csv") -> SubmitResult:
        url = base_url(self.environment).rstrip("/") + endpoint
        for attempt in (1, 2):
            token = await self.get_token(force=attempt == 2)
            headers = {"Authorization": f"Bearer {token}"}
            async with self._http() as http:
                try:
                    if csv_bytes is None:
                        resp = await http.post(url, json=envelope, headers=headers)
                    else:
                        fields = {k: v for k, v in envelope.items() if not isinstance(v, list)}
                        files = {FILE_FIELD: (csv_filename, csv_bytes, "text/csv")}
                        resp = await http.post(url, data=fields, files=files, headers=headers)
                except httpx.HTTPError as exc:
                    raise CBKError(f"Could not reach CBK: {exc}", retryable=True) from exc
            if resp.status_code == 401 and attempt == 1:
                continue  # token likely expired early; log in again once
            body = _body(resp)
            if resp.status_code == 200:
                status_text = request_no = None
                if isinstance(body, dict):
                    status_text = body.get("Status") or body.get("status")
                    rn = body.get("RequestNo") or body.get("requestNo") or body.get("REQUEST_ID")
                    request_no = str(rn) if rn is not None else None
                return SubmitResult(200, status_text or "Submitted", request_no, body)
            message = _error_message(resp.status_code, body)
            raise CBKError(message, http_status=resp.status_code, body=body, retryable=resp.status_code >= 500)
        raise CBKError("CBK rejected the access token twice.", http_status=401)

    async def check_login(self) -> None:
        await self.get_token(force=True)


def _error_message(status: int, body: object) -> str:
    if isinstance(body, dict):
        for k in ("error", "Error", "message", "Message", "detail"):
            if body.get(k):
                v = body[k]
                text = v if isinstance(v, str) else str(v)
                if "MaximumSizeExceeded" in text:
                    return "CBK says the submission is too large (MaximumSizeExceeded). Resend it as CSV or split it."
                if "BadStructure" in text:
                    return "CBK says the submission's structure is wrong (BadStructure)."
                return f"CBK returned {status}: {text}"
    return f"CBK returned {status}: {str(body)[:500]}"
