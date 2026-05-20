# ADR 0001 — OpenFaaS Community as the serverless runtime

**Status**: Accepted
**Date**: 2026-05-19

## Context

The MSPR brief explicitly mandates OpenFaaS for the requested "Scale to Zero" feature. Three serious alternatives existed:

- **Knative Serving** on Kubernetes — more of a CNCF standard, more complex to set up.
- **Managed Cloud Functions** (GCF, Azure Functions, AWS Lambda) — drastically reduces infrastructure complexity but falls outside the requested "Kubernetes" scope.
- **OpenFaaS Community** — targeted by the brief.

## Decision

Use **OpenFaaS Community** with:
- The `dockerfile` template (not `python3-http`) for full control over the image and to allow FastAPI/Uvicorn as the HTTP upstream via `of-watchdog`.
- `faas-cli` as the single build/push/deploy tool.
- Helm to install OpenFaaS on the cluster.

## Consequences

✅ Compliant with the brief.
✅ Active community, rich documentation, native Kubernetes integration.
✅ Scale-to-zero available in the Community version in "idle" mode (configurable duration).

⚠️ No fine-grained multi-tenancy (vs Knative). Acceptable for a single-team PoC.
⚠️ Coupling to `faas-cli` for deployment — migrating to Knative would require rewriting the release workflow.
