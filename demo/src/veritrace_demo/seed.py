"""Idempotent seed: registers the demo companies and creates their users, locations, products, and lots through
the API. Whatever exists already is left as it is, so the seed can run any number of times."""

from __future__ import annotations

import datetime as dt
import logging
from collections import Counter
from dataclasses import dataclass, field

from veritrace_demo.client import Api, ApiError
from veritrace_demo.fixtures import COMPANIES, Company

log = logging.getLogger("veritrace_demo")


class SeedError(RuntimeError):
    """The seed cannot continue, for example because a demo account's password is not the configured one."""


@dataclass
class Seeded:
    """What the seed found or created, by natural key, and how many of each it created or found."""

    users: dict[str, dict] = field(default_factory=dict)  # by email
    locations: dict[str, dict] = field(default_factory=dict)  # by GLN
    products: dict[str, dict] = field(default_factory=dict)  # by GTIN
    lots: dict[str, dict] = field(default_factory=dict)  # by lot number
    created: Counter = field(default_factory=Counter)
    existing: Counter = field(default_factory=Counter)

    def summary(self) -> str:
        kinds = ("tenants", "users", "locations", "products", "lots")
        return ", ".join(f"{kind} {self.created[kind]} created / {self.existing[kind]} existing" for kind in kinds)


def seed(api: Api, password: str, today: dt.date | None = None) -> Seeded:
    """Seed every demo company with the given password for its accounts."""
    today = today or dt.date.today()
    seeded = Seeded()
    for company in COMPANIES:
        seed_company(api, company, password, today, seeded)
    return seeded


def seed_company(api: Api, company: Company, password: str, today: dt.date, seeded: Seeded) -> None:
    register(api, company, password, seeded)
    try:
        token = api.login(company.admin.email, password)
    except ApiError as err:
        raise SeedError(
            f"{company.code} exists, but {company.admin.email} cannot sign in with DEMO_PASSWORD ({err}). "
            "Use the password the stack was seeded with, or start over with `make reset`."
        ) from err

    users = {u["email"]: u for u in api.items("/api/v1/users", token)}
    for a in company.users:
        if a.email in users:
            seeded.existing["users"] += 1
            continue
        users[a.email] = api.post(
            "/api/v1/users", token, {"email": a.email, "password": password, "full_name": a.full_name, "role": a.role}
        )
        seeded.created["users"] += 1
        log.info("created user %s (%s)", a.email, a.role)
    seeded.users.update(users)

    locations = {loc["gln"]: loc for loc in api.items("/api/v1/locations", token)}
    for place in company.locations:
        if place.gln in locations:
            seeded.existing["locations"] += 1
            continue
        locations[place.gln] = api.post("/api/v1/locations", token, place.request())
        seeded.created["locations"] += 1
        log.info("created location %s %s", place.gln, place.name)
    seeded.locations.update(locations)

    products = {p["gtin"]: p for p in api.items("/api/v1/products", token)}
    for item in company.products:
        if item.gtin in products:
            seeded.existing["products"] += 1
            continue
        products[item.gtin] = api.post(
            "/api/v1/products",
            token,
            {
                "gtin": item.gtin,
                "name": item.name,
                "description": item.description,
                "min_temp_celsius": item.min_temp_celsius,
                "max_temp_celsius": item.max_temp_celsius,
            },
        )
        seeded.created["products"] += 1
        log.info("created product %s %s", item.gtin, item.name)
    seeded.products.update(products)

    lots = {lot["lot_number"]: lot for lot in api.items("/api/v1/lots", token)}
    for batch in company.lots:
        if batch.lot_number in lots:
            seeded.existing["lots"] += 1
            continue
        lots[batch.lot_number] = commission(
            api,
            token,
            products[batch.gtin]["id"],
            locations[batch.location_gln]["id"],
            batch.lot_number,
            batch.quantity,
            today,
            batch.shelf_life_days,
        )
        seeded.created["lots"] += 1
        log.info("commissioned lot %s: %d units", batch.lot_number, batch.quantity)
    seeded.lots.update(lots)


def register(api: Api, company: Company, password: str, seeded: Seeded) -> None:
    """Register the company with its headquarters and admin, unless it is registered already."""
    body = {
        "tenant": {
            "code": company.code,
            "legal_name": company.legal_name,
            "tax_code": company.tax_code,
            "gs1_company_prefix": company.gs1_company_prefix,
        },
        "headquarters": company.headquarters.request(),
        "admin": {"email": company.admin.email, "password": password, "full_name": company.admin.full_name},
    }
    try:
        api.post("/api/v1/tenants", body=body)
    except ApiError as err:
        if err.code != "IDENTIFIER_ALREADY_REGISTERED":
            raise
        seeded.existing["tenants"] += 1
        return
    seeded.created["tenants"] += 1
    log.info("registered %s (%s)", company.code, company.legal_name)


def commission(
    api: Api,
    token: str,
    product_id: str,
    location_id: str,
    lot_number: str,
    quantity: int,
    produced: dt.date,
    shelf_life_days: int,
) -> dict:
    """Commission a lot that was produced on a date and keeps for some days."""
    return api.post(
        "/api/v1/lots",
        token,
        {
            "product_id": product_id,
            "lot_number": lot_number,
            "production_date": produced.isoformat(),
            "expiration_date": (produced + dt.timedelta(days=shelf_life_days)).isoformat(),
            "quantity_commissioned": quantity,
            "commissioned_location_id": location_id,
        },
    )
