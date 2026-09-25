# Public Verification and Anti-Counterfeiting (M2)

## 1. Goals

- A consumer scans the QR code on a product and sees where the lot came from, how it was transported and
  kept cold, and whether the record is anchored on-chain.
- The system detects copied labels and forged ones.

## 2. Labels

- The lot owner issues a **label series** for a lot: a contiguous range of serial numbers (AI 21) with the
  tenant's current signing key version. The series records the range. Individual labels are derived
  on demand and not stored.
- Label URI format: [gs1-identifiers.md §4](gs1-identifiers.md#4-gs1-digital-link-m2).
- Signature:

  ```
  message = "v1|" + GTIN + "|" + LOT + "|" + SERIAL
  s       = base64url( truncate_128( HMAC-SHA256(K_tenant,k, message) ) )     // 22 characters
  ```

  - Each tenant has versioned signing keys `K_tenant,k`. Keys are stored encrypted (wrapped by the master
    key) and verified only on the server. The portal never holds keys.
  - A 128-bit tag keeps the QR code small and still makes forgery infeasible.

## 3. Scan verification

The portal forwards each scan to the core public API with:

- the label fields;
- the optional device position, if the consumer consents to browser geolocation;
- otherwise nothing, in which case no location is used.

Verdicts, first match wins:

| Verdict | Condition | Consumer message |
| --- | --- | --- |
| `UNKNOWN` | GTIN or lot not registered, or serial outside every issued series | Product not found |
| `FORGED` | Signature invalid for the stated key version | Label cannot be verified |
| `RECALLED` | Lot status is `RECALLED` | Danger: do not consume; return to the point of sale |
| `SUSPICIOUS_DUPLICATE` | Impossible travel (§4) or more than 20 scans of the same serial within 24 h | Label may have been copied |
| `GENUINE` | Otherwise | Verified product |

Every scan is logged with its verdict. The logged position is rounded to 2 decimal places (~1 km), and the
IP address and user agent are stored only as salted hashes.

## 4. Impossible travel

For the previous located scan `A` and the current located scan `B` of the same serial:

```
speed = haversine(A, B) / max(|t_B − t_A|, 60 s)      // km/h
flag  ⇔ speed > 900 km/h
```

The 60-second floor prevents division by near-zero intervals. Scans without a position are skipped for
this check.

## 5. Public timeline content

The public timeline for a lot exposes:

- product name and GTIN, lot number, production and expiration dates;
- for each shipment of the lot: facility names and cities (not coordinates), event types and times,
  cold-chain compliance (in bounds, or incidents with their duration), and the temperature series at
  15-minute resolution;
- compliance documents: type and plaintext SHA-256 only, never the content;
- for each event and incident: its hash and its on-chain proof status (§6).

It never exposes quantities, user names, tenant internal IDs, or exact coordinates.

## 6. On-chain proof

For any event or incident hash, the portal fetches the inclusion proof from the relayer's public API:
batch ID, Merkle root, proof path, transaction hash, block number, and manifest CID. It links the
transaction to the Polygon Amoy explorer. The proof can also be checked in the browser against the
contract's `verifyLeaf` view function
([ADR-0014](../adr/0014-on-chain-commitments.md)).
