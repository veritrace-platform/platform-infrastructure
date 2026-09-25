# Smart Contract Interface (M2)

The design rationale is in [ADR-0014](../adr/0014-on-chain-commitments.md).

| Property | Value |
| --- | --- |
| Contract | `SupplyChainTraceability` |
| Language | Solidity 0.8.30, EVM target `cancun` |
| Dependencies | OpenZeppelin Contracts 5 (`AccessControl`, `Pausable`, `MerkleProof`) |
| Network | Polygon Amoy testnet (chain ID `80002`) |
| Upgradeability | None. The contract is immutable; a new version means a new deployment. |

```solidity
interface ISupplyChainTraceability {
    struct Batch {
        bytes32 merkleRoot;
        uint32 leafCount;
        uint64 committedAt;   // block timestamp
    }

    /// Emitted once per committed batch.
    event BatchCommitted(
        uint64 indexed batchId,
        bytes32 indexed merkleRoot,
        uint32 leafCount,
        string manifestURI     // ipfs://<CID> of the batch manifest
    );

    error BatchOutOfOrder(uint64 expected, uint64 provided);
    error EmptyBatch();
    error ZeroRoot();

    /// RELAYER_ROLE only; reverts when paused.
    /// batchId must equal lastBatchId() + 1, which keeps commits gapless and makes retries idempotent.
    function commitBatch(
        uint64 batchId,
        bytes32 merkleRoot,
        uint32 leafCount,
        string calldata manifestURI
    ) external;

    function lastBatchId() external view returns (uint64);

    function getBatch(uint64 batchId) external view returns (Batch memory);

    /// True if `leafHash` (a VeriTrace event or incident SHA-256) is included in `batchId`.
    /// Leaf node = keccak256(bytes.concat(keccak256(abi.encode(leafHash)))), verified with
    /// OpenZeppelin MerkleProof (sorted-pair keccak256).
    function verifyLeaf(uint64 batchId, bytes32 leafHash, bytes32[] calldata proof)
        external view returns (bool);
}
```

Roles:

- `DEFAULT_ADMIN_ROLE`: the deployer. It grants and revokes roles and can pause.
- `RELAYER_ROLE`: the relayer's master wallet.

**Batch manifest** (JSON, pinned to IPFS before the commit):

```json
{
  "schema": "veritrace.batch-manifest.v1",
  "batch_id": 42,
  "chain_id": 80002,
  "contract_address": "0x…",
  "merkle_root": "0x…",
  "leaf_encoding": "keccak256(bytes.concat(keccak256(abi.encode(bytes32 leaf_hash))))",
  "leaves": ["…64 hex…", "…"],
  "created_at": "2026-09-01T15:00:00Z"
}
```

Anyone holding the manifest can rebuild the tree and verify the root independently of VeriTrace.
