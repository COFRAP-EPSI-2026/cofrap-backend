# ADR 0003 — Fernet for at-rest encryption

**Status**: Accepted
**Date**: 2026-05-19

## Context

The brief mandates encryption of `password` and `mfa` in the DB. Alternatives evaluated:

- **bcrypt/argon2 (hash)** — incompatible: we need to **decrypt** the password at login (the brief describes a comparison-after-decryption check, not a hash).
- **Bare AES-GCM** (`cryptography.hazmat`) — more control but requires managing nonce, tag, format.
- **Fernet** (`cryptography.fernet`) — standardised high-level wrapper.
- **libsodium / secretbox** — functionally equivalent, but an extra C dependency.

## Decision

**Fernet**:
- Authenticated AES-128-CBC + HMAC-SHA256.
- url-safe base64 token (compatible with MariaDB TEXT without encoding).
- Includes an internal timestamp (useful for future replay detection).
- Minimal API: `Fernet(key).encrypt(plaintext)` / `.decrypt(token)`.

## Consequences

✅ Trivial implementation, small error surface.
✅ The MultiFernet format (already in `cryptography`) enables key rotation with no downtime.
✅ Identifiable tokens (start with `gAAAAA…`), easy to assert in tests.

⚠️ Single symmetric key — losing it = losing the accounts. Mitigation: industrialise via KMS if going to production (see [`security.md`](../security.md#recommendations-for-production)).
⚠️ No automatic rotation implemented in the PoC — a manual operation if needed.
