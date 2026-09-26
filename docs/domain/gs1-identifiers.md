# GS1 Identifiers

VeriTrace identifies organizations' locations, trade items, lots, and logistic units with GS1 keys. Every
service and client validates these keys with the same rules.

## 1. Keys in use

| Key | Identifies | Length | Structure | Source |
| --- | --- | --- | --- | --- |
| **GCP** (GS1 Company Prefix) | A tenant | 6–10 digits | Assigned by a GS1 member organization; Vietnam prefixes start with `893` | Entered at tenant registration |
| **GLN** (Global Location Number) | A physical location (warehouse, hub, headquarters) | 13 | `GCP + location reference + check digit` | Entered by the tenant |
| **GTIN-14** (Global Trade Item Number) | A trade item (product) | 14 | `indicator + GCP + item reference + check digit` | Entered by the tenant |
| **Lot number** (AI 10) | A production batch of one GTIN | 1–20 characters | Free text | Entered by the tenant |
| **Serial number** (AI 21) | One consumer unit within a lot (M2) | 1–20 digits | Numeric sequence | Issued by VeriTrace |
| **SSCC** (Serial Shipping Container Code) | One logistic unit (pallet or container) in one shipment | 18 | `extension digit + GCP + serial reference + check digit` | Issued by VeriTrace |

### Validation rules

- GLN, GTIN, and SSCC contain only ASCII digits, have exactly the length above, and end with a valid
  check digit (§2).
- **Prefix ownership:**
  - A GLN must start with the tenant's GCP.
  - A GTIN-14 must contain the tenant's GCP at positions 2 onward, right after the indicator digit.
  - This stops a tenant from registering identifiers that belong to another company.
- GTIN-14 is the only accepted GTIN form. Clients left-pad GTIN-8/12/13 with zeros before they submit.
  The indicator digit is `0` for a base unit and `1`–`8` for packaging levels.
- A lot number matches `^[0-9A-Za-z._-]{1,20}$`. This is a URL-safe subset of the GS1 AI 10 character
  set, so lot numbers can appear in Digital Link paths without escaping.
- A GCP matches `^[0-9]{6,10}$` and is unique across tenants. VeriTrace does not verify GCP ownership with
  GS1. That check is an onboarding procedure outside the system.

Invalid identifiers are rejected with HTTP 422 and error code `INVALID_GS1_IDENTIFIER`. The error lists the
reason, which is one of `LENGTH`, `NON_NUMERIC`, `CHECK_DIGIT`, or `PREFIX_MISMATCH`.

## 2. Check digit (GS1 Modulo 10)

For a digit string `d₁…dₙ₋₁` (the key without its check digit):

1. Weight the digits from the **rightmost** one: 3, 1, 3, 1, …
2. `S = Σ dᵢ × wᵢ`
3. `check = (10 − (S mod 10)) mod 10`

The same function serves every key length. Reference test vectors are listed below. The machine-readable
set used by the Go and TypeScript test suites is
[`contracts/test-vectors/gs1-check-digit.json`](../contracts/test-vectors/gs1-check-digit.json).

| Payload (without check digit) | Check digit | Full key |
| --- | --- | --- |
| `629104150021` | 3 | `6291041500213` (GS1 published example) |
| `893000100101` | 5 | `8930001001015` (GLN) |
| `0893000100001` | 8 | `08930001000018` (GTIN-14) |
| `08930001000000001` | 8 | `089300010000000018` (SSCC) |
| `893456700001` | 7 | `8934567000017` (GLN) |
| `0893456700101` | 4 | `08934567001014` (GTIN-14) |
| `08934567000000001` | 7 | `089345670000000017` (SSCC) |

## 3. SSCC issuance

VeriTrace generates an SSCC for every shipment:

```
SSCC = extension digit (tenant setting, default 0)
     + GCP
     + serial reference (zero-padded to 16 − len(GCP) digits)
     + check digit
```

- Serial references come from a per-tenant counter that is incremented atomically in the same
  transaction that creates the shipment. They are never reused, including for cancelled shipments.
- The serial space is `10^(16 − len(GCP))`. When it is exhausted, issuance fails with `409 CONFLICT`,
  and the tenant must change its extension digit.

## 4. GS1 Digital Link (M2)

Consumer labels encode a GS1 Digital Link URI:

```
{PUBLIC_TRACE_BASE_URL}/01/{GTIN-14}/10/{LOT}/21/{SERIAL}?k={KEY_VERSION}&s={SIGNATURE}
```

- The path follows the GS1 Digital Link syntax. AI order is `01` → `10` → `21`.
- `k` and `s` are VeriTrace extensions that carry the anti-counterfeiting signature. They are defined in
  [public-verification.md](public-verification.md).
- Shipments (SSCC) never appear on consumer labels. SSCCs identify logistic units, not consumer units.
