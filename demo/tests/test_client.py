import json

import httpx
import pytest

from veritrace_demo import client as client_module
from veritrace_demo.client import Api, ApiError


def api_with(handler) -> Api:
    return Api("http://gateway:8000", transport=httpx.MockTransport(handler))


def problem(status, code, **extra):
    body = {"type": "about:blank", "title": "x", "status": status, "code": code, "trace_id": "4bf92f35", **extra}
    return httpx.Response(status, json=body, headers={"Content-Type": "application/problem+json"})


def test_problems_raise_api_errors():
    api = api_with(lambda request: problem(422, "OUTSIDE_GEOFENCE", detail="too far", distance_meters=2000))
    with pytest.raises(ApiError) as caught:
        api.post("/api/v1/shipments/x/checkpoints", "token", {})
    err = caught.value
    assert (err.status, err.code, err.trace_id) == (422, "OUTSIDE_GEOFENCE", "4bf92f35")
    assert err.problem["distance_meters"] == 2000
    assert "too far" in str(err)


def test_field_errors_are_described():
    errors = [{"field": "gln", "code": "CHECK_DIGIT", "message": "expected 5"}]
    api = api_with(lambda request: problem(422, "INVALID_GS1_IDENTIFIER", errors=errors))
    with pytest.raises(ApiError, match="gln: CHECK_DIGIT"):
        api.post("/api/v1/locations", "token", {})


def test_rate_limits_are_waited_out(monkeypatch):
    waits = []
    monkeypatch.setattr(client_module.time, "sleep", waits.append)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "4"}, json={"code": "RATE_LIMITED"})
        return httpx.Response(200, json={"access_token": "t"})

    api = api_with(handler)
    assert api.login("admin@sgfresh.example", "secret-password") == "t"
    assert waits == [4, 4]


def test_requests_carry_the_token_and_json():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "1"})

    assert api_with(handler).post("/api/v1/users", "abc", {"email": "x"}) == {"id": "1"}
    assert seen == {"auth": "Bearer abc", "body": {"email": "x"}}


def test_items_follow_cursors():
    def handler(request):
        cursor = request.url.params.get("cursor")
        assert request.url.params["limit"] == "100"
        if cursor is None:
            return httpx.Response(200, json={"items": [1, 2], "next_cursor": "c2"})
        return httpx.Response(200, json={"items": [3], "next_cursor": None})

    assert list(api_with(handler).items("/api/v1/lots", "t")) == [1, 2, 3]


def test_each_account_signs_in_once():
    logins = []

    def handler(request):
        logins.append(json.loads(request.content)["email"])
        return httpx.Response(200, json={"access_token": "token-" + logins[-1]})

    api = api_with(handler)
    assert api.login("a@x.example", "p") == api.login("a@x.example", "p") == "token-a@x.example"
    api.login("b@x.example", "p")
    assert logins == ["a@x.example", "b@x.example"]
