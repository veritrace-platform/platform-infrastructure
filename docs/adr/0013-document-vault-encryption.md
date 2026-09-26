# ADR-0013: Document vault encryption (M2)

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

Compliance documents (certificates of origin and quality, inspection reports, invoices) are stored on
IPFS, which is public and content-addressed. They must stay confidential, remain verifiable, and be
streamed back to authorized users without writing plaintext to disk.

A single AES-GCM tag over a whole file only authenticates at the end of the file. A streaming decryptor
would therefore release unauthenticated plaintext.

## Decision

- **Envelope encryption.**
  - Each document gets a fresh random 256-bit data key.
  - The data key is encrypted (wrapped) with the platform master key using AES-256-GCM, and stored in the
    database with the master key ID.
  - The master key comes from configuration (`MASTER_KEY_*`, base64, versioned) and can be moved to a
    cloud KMS without format changes.
- **Chunked AEAD format `VTENC1`**, a STREAM-style construction:

  ```
  header  = "VTENC1" ‖ u8 version(1) ‖ u32 chunk_size(65536) ‖ 7-byte random nonce_prefix
  chunk_i = AES-256-GCM(data_key,
                        nonce = nonce_prefix ‖ u32 counter_i ‖ u8 last_flag,
                        aad   = header,
                        plaintext[i])
  ```

  - Every 64 KiB chunk is authenticated independently. The `last_flag` byte prevents truncation and the
    counter prevents reordering.
  - Nonces never repeat, because every document has a unique key and unique counters.
- **Integrity.** The SHA-256 of the plaintext is computed during upload, stored, and exposed as
  `X-Content-SHA256` on download. It is also included in the `shipment.document_attached` event, so it is
  anchored on-chain.
- **Storage.** Only the ciphertext goes to IPFS, behind one `BlobStore` interface.
  - A **self-hosted Kubo node** is the primary store in every environment.
  - **Pinata** is optional. It is used through Kubo's remote-pinning support, for document CIDs only,
    and only when configured.
  - This keeps the platform within Pinata's free-plan limits
    ([external-services.md](../architecture/external-services.md)).
- **Decryption stream.** The service fetches the ciphertext stream, verifies each chunk before writing its
  plaintext to the response, and aborts the response on any authentication failure.
- **Limits.** Accepted types are PDF, PNG, and JPEG, checked by magic bytes and not only by the declared
  type. Maximum size is 25 MiB.

## Consequences

- IPFS never sees plaintext or keys. Compromising IPFS reveals nothing.
- Decryption is streaming with bounded memory: one chunk at a time.
- Losing the master key makes documents unrecoverable. Master key backup is an operational requirement.
