# ADR-0015: Gasless relayer and chain indexer (M2)

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

End users never hold wallets or pay gas. One platform wallet signs all commitments. Several relayer
workers may run concurrently, and they must never use the same nonce twice. Transactions can stall in the
mempool.

## Decision

- **Inputs.** The relayer consumes `shipment.events` and `telemetry.incidents` from Kafka and stores
  leaves in its own database, idempotently keyed by leaf hash. Core and telemetry never call the relayer
  synchronously.
- **Pipeline.**
  1. The **batcher** seals batches ([ADR-0014](0014-on-chain-commitments.md)), stores proofs, pins the
     manifest, and enqueues a `commit` job on the Redis Stream `relayer:jobs` (consumer group
     `relayer-workers`).
  2. The **worker** claims a job and acquires the nonce lock:
     - The lock is `SET relayer:nonce-lock:{address} <token> NX PX 30000`, released through a
       compare-and-delete Lua script.
     - Under the lock, the worker reads the next nonce from Redis (initialized from `PendingNonceAt` when
       missing), signs an EIP-1559 `commitBatch` transaction, broadcasts it, records it, increments the
       nonce, and releases the lock.
  3. The **tracker** watches pending transactions:
     - If a transaction is unmined after **45 s**, the tracker re-signs it with the **same nonce** and
       both `maxFeePerGas` and `maxPriorityFeePerGas` raised by **15%**. The raise is floored at the
       current network suggestion and capped by `MAX_FEE_PER_GAS_GWEI`.
     - Replacements are recorded, and the job fails after 5 replacements.
  4. The **indexer** subscribes to `BatchCommitted` over WebSocket RPC and backfills with `eth_getLogs`
     from `chain_cursors`. A batch is marked `CONFIRMED` only when its block is at or below the chain's
     `finalized` block.
- **Networks.** Development and integration tests use a local **Anvil** chain (`web3` compose profile;
  instant blocks, no faucet). Only deployed environments use Polygon Amoy. The chain is selected by
  configuration (`CHAIN_ID`, `RPC_URL`, `WS_RPC_URL`, `CONTRACT_ADDRESS`).
- **Key custody.** In development the master key comes from `RELAYER_PRIVATE_KEY`. It is never logged,
  and the process refuses to start if the key is missing. The deployed contract grants `RELAYER_ROLE` to
  this address only.
- **Public API.** Proof lookups by leaf hash, consumed by the dashboard and the public portal.

## Consequences

- Nonce safety holds for any number of workers. The lock covers only signing and broadcasting, not
  confirmation waits.
- Using Redis Streams gives acknowledgement and redelivery (`XAUTOCLAIM`) for crashed workers.
- The relayer is the only component that needs chain credentials or RPC endpoints.
