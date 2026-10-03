"""The demo world: four companies around a chilled-milk supply chain in Ho Chi Minh City, and one in Hanoi that
takes part in none of it.

- Saigon Fresh Foods (SGFRESH) makes dairy and frozen goods and ships them from its Tan Thuan cold store.
- Mekong Cold Chain Logistics (MEKONG_COLD) carries them; its driver picks up, checks in at the Thu Duc depot,
  and delivers.
- District 7 Fresh Mart (D7MART) receives them at its store hub.
- Hanoi Dairy (HANOI_DAIRY) is another tenant of the platform, which must see nothing of the others.

Every GS1 key starts with its company's prefix and has a valid check digit. The cold store and the store hub lie at
the two ends of the simulator's default route, so simulated readings travel from origin to destination.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    email: str
    full_name: str
    role: str


@dataclass(frozen=True)
class Place:
    gln: str
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    geo_fence_radius_meters: int = 200

    def request(self) -> dict:
        return {
            "gln": self.gln,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "country_code": "VN",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "geo_fence_radius_meters": self.geo_fence_radius_meters,
        }


@dataclass(frozen=True)
class Item:
    gtin: str
    name: str
    description: str
    min_temp_celsius: float
    max_temp_celsius: float


@dataclass(frozen=True)
class Batch:
    lot_number: str
    gtin: str
    quantity: int
    shelf_life_days: int
    location_gln: str


@dataclass(frozen=True)
class Company:
    code: str
    legal_name: str
    tax_code: str
    gs1_company_prefix: str
    headquarters: Place
    admin: Account
    users: tuple[Account, ...] = ()
    locations: tuple[Place, ...] = ()
    products: tuple[Item, ...] = ()
    lots: tuple[Batch, ...] = ()

    @property
    def accounts(self) -> tuple[Account, ...]:
        return (self.admin, *self.users)


TAN_THUAN_COLD_STORE = Place(
    gln="8930001000025",
    name="Tan Thuan cold store",
    address="Lot 12, Tan Thuan Export Processing Zone, District 7",
    city="Ho Chi Minh City",
    latitude=10.7627,
    longitude=106.7429,
    geo_fence_radius_meters=300,
)

FRESH_MILK = Item(
    gtin="08930001000018",
    name="Pasteurized fresh milk 1 L",
    description="Whole milk, pasteurized; keep at 2–8 °C",
    min_temp_celsius=2,
    max_temp_celsius=8,
)

SAIGON_FRESH = Company(
    code="SGFRESH",
    legal_name="Saigon Fresh Foods Joint Stock Company",
    tax_code="0312345678",
    gs1_company_prefix="8930001",
    headquarters=Place(
        gln="8930001001015",
        name="Saigon Fresh Foods head office",
        address="12 Nguyen Hue, District 1",
        city="Ho Chi Minh City",
        latitude=10.773547,
        longitude=106.703945,
    ),
    admin=Account("admin@sgfresh.example", "Nguyen Van An", "ADMIN"),
    users=(Account("warehouse@sgfresh.example", "Le Thi Hoa", "WAREHOUSE_MANAGER"),),
    locations=(TAN_THUAN_COLD_STORE,),
    products=(
        FRESH_MILK,
        Item(
            gtin="08930001000025",
            name="Natural yogurt 4 x 100 g",
            description="Set yogurt, four cups; keep at 2–6 °C",
            min_temp_celsius=2,
            max_temp_celsius=6,
        ),
        Item(
            gtin="08930001000032",
            name="Frozen basa fillet 1 kg",
            description="Individually quick frozen; keep at -25 to -18 °C",
            min_temp_celsius=-25,
            max_temp_celsius=-18,
        ),
    ),
    lots=(
        Batch("L2026-MILK-01", "08930001000018", 2000, 14, TAN_THUAN_COLD_STORE.gln),
        Batch("L2026-YOG-01", "08930001000025", 1000, 21, TAN_THUAN_COLD_STORE.gln),
        Batch("L2026-BASA-01", "08930001000032", 500, 180, TAN_THUAN_COLD_STORE.gln),
    ),
)

THU_DUC_DEPOT = Place(
    gln="8935002000012",
    name="Thu Duc cold depot",
    address="45 Xa Lo Ha Noi, Thu Duc",
    city="Ho Chi Minh City",
    latitude=10.8502,
    longitude=106.7719,
    geo_fence_radius_meters=300,
)

MEKONG_COLD = Company(
    code="MEKONG_COLD",
    legal_name="Mekong Cold Chain Logistics Company Limited",
    tax_code="0315550123",
    gs1_company_prefix="8935002",
    headquarters=THU_DUC_DEPOT,
    admin=Account("admin@mekongcold.example", "Pham Minh Quan", "ADMIN"),
    users=(
        Account("dispatch@mekongcold.example", "Vo Thanh Tam", "WAREHOUSE_MANAGER"),
        Account("driver@mekongcold.example", "Tran Van Binh", "DRIVER"),
    ),
)

DISTRICT_7_HUB = Place(
    gln="8934567000017",
    name="District 7 store hub",
    address="88 Nguyen Thi Thap, District 7",
    city="Ho Chi Minh City",
    latitude=10.7296,
    longitude=106.7188,
    geo_fence_radius_meters=250,
)

D7_MART = Company(
    code="D7MART",
    legal_name="District 7 Fresh Mart Company Limited",
    tax_code="0309876543",
    gs1_company_prefix="8934567",
    headquarters=DISTRICT_7_HUB,
    admin=Account("admin@d7mart.example", "Do Thu Trang", "ADMIN"),
    users=(Account("dock@d7mart.example", "Huynh Quoc Bao", "WAREHOUSE_MANAGER"),),
)

HANOI_DAIRY = Company(
    code="HANOI_DAIRY",
    legal_name="Hanoi Dairy Corporation",
    tax_code="0101234567",
    gs1_company_prefix="8936003",
    headquarters=Place(
        gln="8936003000018",
        name="Hanoi Dairy plant",
        address="Km 12, Thang Long Boulevard, Hoai Duc",
        city="Hanoi",
        latitude=21.0285,
        longitude=105.8048,
    ),
    admin=Account("admin@hanoidairy.example", "Bui Duc Long", "ADMIN"),
    products=(
        Item(
            gtin="08936003000018",
            name="UHT milk 180 ml",
            description="Ultra-high-temperature milk; keep below 25 °C",
            min_temp_celsius=4,
            max_temp_celsius=25,
        ),
    ),
)

COMPANIES: tuple[Company, ...] = (SAIGON_FRESH, MEKONG_COLD, D7_MART, HANOI_DAIRY)

# The roles each company plays in the scenario.
OWNER = SAIGON_FRESH
CARRIER = MEKONG_COLD
CONSIGNEE = D7_MART
OUTSIDER = HANOI_DAIRY
ORIGIN = TAN_THUAN_COLD_STORE
CHECKPOINT = THU_DUC_DEPOT
DESTINATION = DISTRICT_7_HUB
PRODUCT = FRESH_MILK


def account_with_role(company: Company, role: str) -> Account:
    """Return the first account of the company with the role."""
    for a in company.accounts:
        if a.role == role:
            return a
    raise KeyError(f"{company.code} has no {role}")
