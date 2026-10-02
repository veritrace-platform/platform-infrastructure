import math
import re

from veritrace_simulator.gs1 import check_digit
from veritrace_simulator.scenario import DEFAULT_FROM, DEFAULT_TO

from veritrace_demo import fixtures as f

ROLES = {"ADMIN", "WAREHOUSE_MANAGER", "DRIVER", "INSPECTOR"}


def valid_key(key: str, length: int) -> bool:
    return len(key) == length and key.isdigit() and check_digit(key[:-1]) == int(key[-1])


def meters(lat1, lng1, lat2, lng2):
    """Haversine distance, as core computes geo-fences."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def test_gs1_keys_are_valid_and_owned():
    for company in f.COMPANIES:
        prefix = company.gs1_company_prefix
        for place in (company.headquarters, *company.locations):
            assert valid_key(place.gln, 13), place.gln
            assert place.gln.startswith(prefix), place.gln
        for item in company.products:
            assert valid_key(item.gtin, 14), item.gtin
            assert item.gtin[1:].startswith(prefix), item.gtin


def test_identifiers_are_unique():
    def unique(values):
        values = list(values)
        return len(values) == len(set(values))

    companies = f.COMPANIES
    assert unique(c.code for c in companies)
    assert unique(c.tax_code for c in companies)
    assert unique(c.gs1_company_prefix for c in companies)
    assert unique(a.email for c in companies for a in c.accounts)
    assert unique(p.gln for c in companies for p in (c.headquarters, *c.locations))
    assert unique(i.gtin for c in companies for i in c.products)
    assert unique(lot.lot_number for c in companies for lot in c.lots)


def test_companies_follow_the_api_rules():
    for company in f.COMPANIES:
        assert re.fullmatch(r"[A-Z0-9_]{3,32}", company.code)
        assert re.fullmatch(r"[0-9]{10}(-[0-9]{3})?", company.tax_code)
        assert [a.role for a in company.accounts].count("ADMIN") == 1
        assert company.admin.role == "ADMIN"
        assert all(a.role in ROLES for a in company.accounts)
        for item in company.products:
            assert -50 <= item.min_temp_celsius < item.max_temp_celsius <= 80
        glns = {p.gln for p in (company.headquarters, *company.locations)}
        gtins = {i.gtin for i in company.products}
        for lot in company.lots:
            assert re.fullmatch(r"[0-9A-Za-z._-]{1,20}", lot.lot_number)
            assert lot.gtin in gtins and lot.location_gln in glns and lot.quantity > 0


def test_the_scenario_cast():
    assert f.ORIGIN in f.OWNER.locations
    assert f.CARRIER.headquarters == f.CHECKPOINT
    assert f.CONSIGNEE.headquarters == f.DESTINATION
    assert f.PRODUCT in f.OWNER.products
    assert (f.PRODUCT.min_temp_celsius, f.PRODUCT.max_temp_celsius) == (2, 8)
    for company, role in [(f.OWNER, "WAREHOUSE_MANAGER"), (f.CARRIER, "DRIVER"), (f.CONSIGNEE, "WAREHOUSE_MANAGER")]:
        assert f.account_with_role(company, role).role == role


def test_simulated_readings_travel_from_origin_to_destination():
    # The simulator's default route starts in the origin's geo-fence and ends in the destination's.
    assert meters(*DEFAULT_FROM, f.ORIGIN.latitude, f.ORIGIN.longitude) < f.ORIGIN.geo_fence_radius_meters
    assert meters(*DEFAULT_TO, f.DESTINATION.latitude, f.DESTINATION.longitude) < f.DESTINATION.geo_fence_radius_meters
