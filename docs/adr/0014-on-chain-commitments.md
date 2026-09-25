# ADR-0014: On-chain commitments (M2)

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The draft committed a Merkle root per shipment and status change, and stored SSCC strings on-chain. This
has four problems:

- It is effectively one transaction per event, not batching.
- It publishes business identifiers and shipment volumes on a public chain.
- `string indexed` event parameters are stored only as hashes, so an indexer cannot read them back.
- SHA-256 internal nodes are incompatible with the standard Solidity Merkle verification library.

## Decision

- **Epoch batching.** The relayer collects leaf hashes (shipment `event_hash` and incident
  `incident_hash`) and seals a batch when the first of these happens:
  - 10 minutes have passed since the oldest pending leaf;
  - 1024 leaves are pending;
  - a **priority** leaf (a recall event) arrives, in which case the batch is sealed immediately.
- **Tree construction** is compatible with OpenZeppelin `StandardMerkleTree`:
  - `leaf node = keccak256(bytes.concat(keccak256(abi.encode(bytes32 leafHash))))`, a double hash that
    prevents second-preimage attacks;
  - leaf nodes are sorted;
  - internal nodes use the commutative `keccak256(sorted pair)`.
- **Contract:** `commitBatch(batchId, root, leafCount, manifestURI)` with strictly sequential `batchId`,
  plus the `verifyLeaf` view. The full interface is in [smart-contract.md](../contracts/smart-contract.md).
- **Transparency:** each batch's manifest (the ordered leaf list) is pinned to IPFS and referenced by the
  commit, so third parties can verify without trusting VeriTrace's API.
- **Nothing identifying goes on-chain.** Only roots, counts, and manifest URIs are published. Leaf hashes
  of events are unlinkable without the off-chain data.

## Consequences

- Cost is one transaction per epoch regardless of volume.
- Anchoring latency is up to 10 minutes, or seconds for recalls. The UI shows `PENDING` until then.
- Sequential batch IDs make a retried or sped-up commit fail harmlessly if an earlier attempt was already
  mined.
