"""Minimal Famulor API v1 client used by the Dify tools.

Only fixed, documented HTTPS endpoints under ``<base_url>/api/v1`` are called.
Write requests are never retried, so a call or campaign is never started twice.
"""

from __future__ import annotations

import time
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

import httpx

DEFAULT_BASE_URL = "https://app.famulor.io"
USER_AGENT = "famulor-dify-plugin/0.1.1"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class FamulorAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def normalize_base_url(value: str | None) -> str:
    raw = (value or "").strip() or DEFAULT_BASE_URL
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    if parts.scheme != "https":
        raise FamulorAPIError("Base URL must use https://")
    if not parts.hostname or parts.username or parts.password:
        raise FamulorAPIError("Base URL must be a plain host such as https://app.famulor.io")
    path = parts.path.rstrip("/")
    if path in ("", "/api/v1"):
        path = "/api/v1"
    else:
        raise FamulorAPIError("Base URL must be the workspace domain only, e.g. https://app.famulor.io")
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    return f"https://{host}{path}"


def seg(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise FamulorAPIError("An id is required.")
    return quote(text, safe="")


_FRIENDLY = {
    401: "The Famulor API key or token is invalid, expired or revoked.",
    403: "Famulor denied the request (missing scope, role or plan feature such as API Access).",
    404: "The requested Famulor resource was not found in this workspace.",
    429: "Famulor rate limit reached. Please retry later.",
}


class FamulorClient:
    def __init__(self, api_key: str, base_url: str | None = None, *, transport: httpx.BaseTransport | None = None,
                 max_read_retries: int = 2) -> None:
        if not api_key or not str(api_key).strip():
            raise FamulorAPIError("A Famulor API key (fam_...) is required.")
        self.base_url = normalize_base_url(base_url)
        self._headers = {
            "Authorization": f"Bearer {str(api_key).strip()}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        self._http = httpx.Client(timeout=TIMEOUT, transport=transport, follow_redirects=False)
        self._retries = max_read_retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "FamulorClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, json: Any = None) -> Any:
        method = method.upper()
        clean = {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in (params or {}).items() if v not in (None, "")}
        url = f"{self.base_url}/{path.lstrip('/')}"
        attempt = 0
        while True:
            try:
                resp = self._http.request(method, url, params=clean or None, json=json, headers=self._headers)
            except httpx.TimeoutException as e:
                if method == "GET" and attempt < self._retries:
                    attempt += 1
                    time.sleep(0.5 * attempt)
                    continue
                raise FamulorAPIError("Famulor did not respond in time.") from e
            except httpx.HTTPError as e:
                if method == "GET" and attempt < self._retries:
                    attempt += 1
                    time.sleep(0.5 * attempt)
                    continue
                raise FamulorAPIError(f"Could not reach Famulor: {type(e).__name__}") from e
            if resp.is_success:
                if not resp.content:
                    return None
                body = resp.json()
                return body.get("data", body) if isinstance(body, dict) else body
            if method == "GET" and resp.status_code in (429, 502, 503, 504) and attempt < self._retries:
                attempt += 1
                time.sleep(_retry_after(resp, attempt))
                continue
            raise _error(resp)

    # ---- typed helpers -------------------------------------------------
    def me(self) -> Any:
        return self.request("GET", "/me")

    def list_assistants(self, limit: int = 50, offset: int = 0) -> Any:
        return self.request("GET", "/assistants", params={"limit": limit, "offset": offset})

    def create_call(self, body: Mapping[str, Any]) -> Any:
        return self.request("POST", "/calls", json=dict(body))

    def get_call(self, call_id: str) -> Any:
        return self.request("GET", f"/calls/{seg(call_id)}")

    def list_calls(self, **params: Any) -> Any:
        return self.request("GET", "/calls", params=params)

    def create_contact(self, body: Mapping[str, Any]) -> Any:
        return self.request("POST", "/leads", json=dict(body))

    def list_campaigns(self, **params: Any) -> Any:
        return self.request("GET", "/campaigns", params=params)

    def start_campaign(self, campaign_id: str) -> Any:
        return self.request("POST", f"/campaigns/{seg(campaign_id)}/start")


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    try:
        return min(float(resp.headers.get("retry-after", "")), 30.0)
    except ValueError:
        return min(0.5 * (2**attempt), 8.0)


def _error(resp: httpx.Response) -> FamulorAPIError:
    code = None
    message = None
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            code = err.get("code")
            message = err.get("message")
    except ValueError:
        pass
    friendly = _FRIENDLY.get(resp.status_code)
    text = message or friendly or f"Famulor request failed with HTTP {resp.status_code}."
    if friendly and message and resp.status_code in (401, 403):
        text = f"{friendly} ({message})"
    return FamulorAPIError(text, status_code=resp.status_code, code=code)


def transcript_turns(call: Mapping[str, Any]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    display = call.get("transcript_display")
    if isinstance(display, list):
        for item in display:
            if isinstance(item, dict) and item.get("kind") in (None, "message") and item.get("text"):
                turns.append({"role": str(item.get("role") or "unknown"), "text": str(item["text"])})
    if turns:
        return turns
    raw = call.get("transcript")
    if isinstance(raw, dict):
        raw = raw.get("items")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                text = item.get("content", item.get("text"))
                if isinstance(text, list):
                    text = " ".join(str(t) for t in text)
                if text:
                    turns.append({"role": str(item.get("role") or "unknown"), "text": str(text)})
    if not turns and isinstance(call.get("structured_transcript"), str):
        for line in call["structured_transcript"].splitlines():
            if line.strip():
                role, sep, text = line.partition(":")
                turns.append({"role": role.strip().lower(), "text": text.strip()} if sep and text.strip()
                             else {"role": "unknown", "text": line.strip()})
    return turns


def client_from_credentials(credentials: Mapping[str, Any], **kw: Any) -> FamulorClient:
    return FamulorClient(str(credentials.get("api_key") or ""), credentials.get("base_url") or None, **kw)


# ---- helpers shared by the Dify tools ---------------------------------------

def clamp_limit(value: Any, default: int) -> int:
    try:
        n = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, 200))


def opt_str(params: Mapping[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_str(params: Mapping[str, Any], key: str, label: str) -> str:
    value = opt_str(params, key)
    if not value:
        raise FamulorAPIError(f"{label} is required.")
    return value


CALL_SUMMARY_FIELDS = (
    "id", "assistant_id", "direction", "from_number", "to_number", "status", "started_at", "ended_at",
    "duration_sec", "summary", "sentiment", "success", "created_at",
)


def call_summary(call: Mapping[str, Any]) -> dict[str, Any]:
    out = {k: call.get(k) for k in CALL_SUMMARY_FIELDS if k in call}
    if call.get("failure"):
        out["failure"] = call["failure"]
    return out
