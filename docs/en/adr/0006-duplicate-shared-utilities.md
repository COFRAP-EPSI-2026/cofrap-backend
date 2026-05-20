# ADR 0006 — Duplication of shared modules across functions

**Status**: Accepted
**Date**: 2026-05-19

## Context

`db.py`, `crypto.py` and `qr.py` have identical logic across the 3 OpenFaaS functions. Options to avoid duplication:

1. **Private Python package** published to a registry (private PyPI, GitHub Packages) — heavy workflow for 80 lines of code.
2. **Shared build context** where each function COPYs `../shared/` — requires building from the repo root, breaks the native `faas-cli` workflow.
3. **Symbolic links** during the build — not portable on Windows, fragile.
4. **Controlled duplication**: each function embeds its own copies.

## Decision

**Option 4**: each `functions/<name>/` folder is self-contained. The 3 copies of `db.py`/`crypto.py`/`qr.py` must be kept in sync.

## Consequences

✅ `faas-cli build -f <fn>.yml` works with no custom config.
✅ The `Dockerfile` is trivial and standalone.
✅ Easy to read: everything a function needs is in its folder.

⚠️ **Drift risk** between the copies. Mitigations:
- Shared unit tests (`tests/unit/test_shared_modules.py`) validate the contract from the `generate-password` copy — if it drifts, the test breaks.
- If drift becomes a practical problem, switch to option 2 with a build context at the repo root (edit `stack.yml` and all `Dockerfile`s).

## Notes

This decision is explicitly temporary — suited to a 3-function PoC. Beyond 5-6 functions, rethink it to publish a shared package.
