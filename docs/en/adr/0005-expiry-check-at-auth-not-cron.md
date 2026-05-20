# ADR 0005 — Expiry checked at authentication, not via a cron job

**Status**: Accepted
**Date**: 2026-05-19

## Context

The brief mandates a 6-month rotation. Two possible strategies:

1. **Batch job / Kubernetes CronJob** that sets `expired = 1` on accounts whose `gendate < now - 6 months`.
2. **Check inside `authenticate-user`**: on every login, compare `now - gendate` against the window.

## Decision

**Option 2**: the `authenticate-user` function computes the account's freshness at login time. If stale, it flips `expired = 1` in the DB and returns `action: regenerate_password_and_2fa` to the frontend.

## Consequences

✅ No dependency on a scheduler — no K8s CronJob to maintain.
✅ No window where an account would be "expired in the DB but undetected": the check is effective at the moment the user tries to log in.
✅ An abandoned account (never reused) stays `expired = 0` — consistent: nothing happens as long as nobody uses it.

⚠️ No global visibility (how many accounts would be expired at a given instant) without an ad-hoc SQL query. Acceptable for a PoC with no audit dashboard.
⚠️ If multiple systems queried `expired`, they would see inconsistent values until a login occurs. Possible mitigation: add a read-only "preview" job if needed.
