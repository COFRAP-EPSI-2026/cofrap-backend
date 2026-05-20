# ADR 0002 — FastAPI/Uvicorn as the upstream of of-watchdog HTTP

**Status**: Accepted
**Date**: 2026-05-19

## Context

OpenFaaS offers several ways to run Python:

1. Official `python3-http` template (Flask under the hood).
2. `python3-debian` template (Flask + native libs).
3. **Custom image** with `of-watchdog` in HTTP mode, forwarding to a local upstream.

The COFRAP brief recommends FastAPI; FastAPI has no official OpenFaaS template.

## Decision

**Option 3**: a custom `Dockerfile` with `of-watchdog` HTTP mode forwarding to `127.0.0.1:5000` where Uvicorn / FastAPI runs.

```dockerfile
ENV fprocess="uvicorn main:app --host 127.0.0.1 --port 5000"
ENV upstream_url="http://127.0.0.1:5000"
ENV mode="http"
CMD ["fwatchdog"]
```

## Consequences

✅ FastAPI keeps all its features: Pydantic validation, free OpenAPI, async/await possible.
✅ of-watchdog in HTTP mode keeps the Uvicorn process warm between requests (no fork-exec per request).
✅ Native Docker healthcheck `wget /healthz`.

⚠️ Image slightly larger than the official templates (~150 MB vs ~80 MB).
⚠️ The Uvicorn warm-up (~500 ms) adds cold start. Acceptable for the PoC; to be measured if the product goes to production.
