import datetime as dt
import itertools
import json
from collections import Counter

import httpx
import pytest

from veritrace_demo import fixtures
from veritrace_demo.client import Api
from veritrace_demo.seed import SeedError, seed

PASSWORD = "veritrace-demo-2026"


class FakeCore:
    """Enough of core's API for the seed: tenants, sign-in, and the collections of each tenant."""

    def __init__(self, password: str = PASSWORD):
        self.password = password
        self.ids = itertools.count(1)
        self.tenants = {}  # code -> tenant id
        self.users = {}  # email -> (tenant id, user)
        self.collections = {"locations": [], "products": [], "lots": []}  # items with "tenant"
        self.posts = Counter()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1/")
        body = json.loads(request.content) if request.content else None
        if request.method == "POST":
            self.posts[path] += 1
        if path == "tenants":
            return self.register(body)
        if path == "auth/login":
            user = self.users.get(body["email"])
            if user is None or self.password != body["password"]:
                return httpx.Response(401, json={"code": "INVALID_CREDENTIALS", "status": 401})
            return httpx.Response(200, json={"access_token": "token:" + body["email"]})
        tenant = self.users[request.headers["Authorization"].removeprefix("Bearer token:")][0]
        if path == "users":
            if request.method == "GET":
                return self.page([u for t, u in self.users.values() if t == tenant])
            user = {"id": f"u{next(self.ids)}", "email": body["email"], "role": body["role"]}
            self.users[body["email"]] = (tenant, user)
            return httpx.Response(201, json=user)
        if request.method == "GET":
            return self.page([i for i in self.collections[path] if i["tenant"] == tenant])
        item = {"id": f"{path}{next(self.ids)}", "tenant": tenant, "status": "ACTIVE", **body}
        self.collections[path].append(item)
        return httpx.Response(201, json=item)

    def register(self, body):
        code = body["tenant"]["code"]
        if code in self.tenants:
            return httpx.Response(409, json={"code": "IDENTIFIER_ALREADY_REGISTERED", "status": 409})
        tenant = self.tenants[code] = f"t{next(self.ids)}"
        admin = body["admin"]
        self.users[admin["email"]] = (tenant, {"id": f"u{next(self.ids)}", "email": admin["email"], "role": "ADMIN"})
        self.collections["locations"].append({"id": f"loc{next(self.ids)}", "tenant": tenant, **body["headquarters"]})
        return httpx.Response(201, json={"tenant": {"code": code}})

    @staticmethod
    def page(items):
        return httpx.Response(200, json={"items": items, "next_cursor": None})


def run_seed(core):
    api = Api("http://gateway:8000", transport=httpx.MockTransport(core))
    try:
        return seed(api, PASSWORD, today=dt.date(2026, 10, 2))
    finally:
        api.close()


def test_seed_creates_the_demo_world_once():
    core = FakeCore()
    first = run_seed(core)
    companies = fixtures.COMPANIES
    assert first.created["tenants"] == len(companies)
    assert first.created["users"] == sum(len(c.users) for c in companies)
    assert first.created["locations"] == sum(len(c.locations) for c in companies)
    assert first.created["products"] == sum(len(c.products) for c in companies)
    assert first.created["lots"] == sum(len(c.lots) for c in companies)
    lot = next(i for i in core.collections["lots"] if i["lot_number"] == "L2026-MILK-01")
    assert (lot["production_date"], lot["expiration_date"]) == ("2026-10-02", "2026-10-16")
    assert lot["product_id"] == first.products[fixtures.PRODUCT.gtin]["id"]
    assert lot["commissioned_location_id"] == first.locations[fixtures.ORIGIN.gln]["id"]

    posts = Counter(core.posts)
    second = run_seed(core)
    # The second run registers nothing new and creates nothing: it only signs in again.
    assert sum(second.created.values()) == 0
    assert second.existing == first.created
    new_posts = core.posts - posts
    assert set(new_posts) == {"tenants", "auth/login"}
    assert second.users.keys() == first.users.keys()


def test_seed_explains_a_password_that_does_not_match():
    core = FakeCore()
    run_seed(core)
    core.password = "another-password-1"
    with pytest.raises(SeedError, match="DEMO_PASSWORD"):
        run_seed(core)
