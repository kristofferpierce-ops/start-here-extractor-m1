from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping
from urllib import error, request

from ..errors import RemoteAuthError, RemoteNotFoundError, RemoteProviderError, RemoteRateLimitError, RetryableOperationError
from ..net.retry import with_retries
from ..types import RetryDecision, RetryPolicy


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> object:
        return json.loads(self.text)


Requestor = Callable[[str, str, Mapping[str, str] | None, bytes | None, float], HttpResponse]


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def urllib_requestor(method: str, url: str, headers: Mapping[str, str] | None = None, data: bytes | None = None, timeout: float = 30.0) -> HttpResponse:
    req = request.Request(url, data=data, headers=dict(headers or {}), method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return HttpResponse(status_code=getattr(resp, 'status', 200), headers={k: v for k, v in resp.headers.items()}, body=resp.read())
    except error.HTTPError as exc:
        headers = {k: v for k, v in exc.headers.items()} if exc.headers else {}
        if exc.code == 401 or exc.code == 403:
            raise RemoteAuthError(f"http-auth-error:{exc.code}", status_code=exc.code, headers=headers) from exc
        if exc.code == 404:
            raise RemoteNotFoundError(f"http-not-found:{exc.code}", status_code=exc.code, headers=headers) from exc
        if exc.code in RETRYABLE_STATUS_CODES:
            raise RemoteRateLimitError(
                f"http-retryable-error:{exc.code}",
                retry_after_seconds=headers.get('Retry-After'),
                status_code=exc.code,
                headers=headers,
            ) from exc
        raise RemoteProviderError(f"http-error:{exc.code}", status_code=exc.code, headers=headers) from exc
    except error.URLError as exc:
        raise RetryableOperationError(f"url-error:{exc.reason}") from exc


def request_json(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    payload: object | None = None,
    timeout: float = 30.0,
    requestor: Requestor = urllib_requestor,
    retry_policy: RetryPolicy | None = None,
    on_retry: Callable[[RetryDecision, Exception], None] | None = None,
) -> dict[str, object]:
    final_headers = {"Accept": "application/json", **dict(headers or {})}
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        final_headers.setdefault("Content-Type", "application/json")

    def _do() -> HttpResponse:
        return requestor(method, url, final_headers, body, timeout)

    response = with_retries(_do, policy=retry_policy, on_retry=on_retry)
    parsed = response.json()
    if not isinstance(parsed, dict):
        raise RemoteProviderError("json-response-was-not-an-object", status_code=response.status_code, headers=response.headers)
    return parsed


def atomic_download(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    dest_path: str | Path,
    timeout: float = 30.0,
    requestor: Requestor = urllib_requestor,
    retry_policy: RetryPolicy | None = None,
    on_retry: Callable[[RetryDecision, Exception], None] | None = None,
) -> str:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _do() -> HttpResponse:
        return requestor(method, url, dict(headers or {}), None, timeout)

    response = with_retries(_do, policy=retry_policy, on_retry=on_retry)
    fd, tmp_name = tempfile.mkstemp(prefix=dest.name + '.', suffix='.part', dir=str(dest.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(response.body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, dest)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return str(dest)
