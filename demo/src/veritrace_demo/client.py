"""A small client of the VeriTrace REST API (docs/contracts/rest-api.md): problem details as exceptions, rate
limits honoured, collections read page by page, and one sign-in per account."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

log = logging.getLogger("veritrace_demo")

MAX_RATE_LIMIT_WAITS = 5


class ApiError(Exception):
    """An RFC 9457 problem answered by the API."""

    def __init__(self, status: int, problem: dict) -> None:
        self.status = status
        self.problem = problem
        self.code: str = problem.get("code", "")
        self.trace_id: str = problem.get("trace_id", "")
        detail = problem.get("detail") or problem.get("title") or ""
        fields = ", ".join(f"{e.get('field')}: {e.get('code')}" for e in problem.get("errors") or [])
        super().__init__(f"{status} {self.code}: {detail}" + (f" ({fields})" if fields else ""))


class Api:
    """Calls the API at base_url, for example http://localhost:8000 (the gateway)."""

    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None, timeout: float = 15.0) -> None:
        self._http = httpx.Client(base_url=base_url.rstrip("/"), transport=transport, timeout=timeout)
        self._tokens: dict[str, str] = {}

    def close(self) -> None:
        self._http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: Any = None,
        params: dict | None = None,
    ) -> Any:
        """Send a request and return the decoded body, or None for an empty one. A problem raises ApiError; 429
        is waited out as Retry-After says."""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for attempt in range(MAX_RATE_LIMIT_WAITS + 1):
            response = self._http.request(method, path, headers=headers, json=json, params=params)
            if response.status_code != httpx.codes.TOO_MANY_REQUESTS or attempt == MAX_RATE_LIMIT_WAITS:
                break
            wait = int(response.headers.get("Retry-After", "6"))
            log.info("rate limited on %s %s; waiting %d s", method, path, wait)
            time.sleep(wait)
        if response.is_error:
            try:
                problem = response.json()
            except ValueError:
                problem = {"detail": response.text[:200]}
            raise ApiError(response.status_code, problem if isinstance(problem, dict) else {})
        if not response.content:
            return None
        return response.json()

    def get(self, path: str, token: str | None = None, **params: Any) -> Any:
        return self.request("GET", path, token=token, params=params or None)

    def post(self, path: str, token: str | None = None, body: Any = None) -> Any:
        return self.request("POST", path, token=token, json=body)

    def items(self, path: str, token: str, **params: Any) -> Iterator[dict]:
        """Yield every item of a collection, following next_cursor."""
        params.setdefault("limit", 100)
        while True:
            page = self.get(path, token, **params)
            yield from page["items"]
            if not page.get("next_cursor"):
                return
            params["cursor"] = page["next_cursor"]

    def login(self, email: str, password: str) -> str:
        """Sign in once per account and return its access token, which lasts 15 minutes."""
        if email not in self._tokens:
            session = self.post("/api/v1/auth/login", body={"email": email, "password": password})
            self._tokens[email] = session["access_token"]
        return self._tokens[email]
