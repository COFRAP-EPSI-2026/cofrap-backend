# ADR 0004 — MariaDB as a StatefulSet and raw SQL (no ORM)

**Status**: Accepted
**Date**: 2026-05-19

## Context

DB hosting choice:

- Dedicated VM outside the cluster — autonomy, but an external resource to manage.
- Managed cloud DB (Cloud SQL, RDS) — not available in the academic PoC context.
- **Kubernetes StatefulSet** — homogeneous with the rest of the deployment.

Python access choice:

- SQLAlchemy / Tortoise ORM — declarative modelling, migrations.
- Raw driver (PyMySQL, `mariadb`) — direct code, fewer dependencies.

## Decision

- MariaDB as a **StatefulSet** with a 2 Gi PVC, official `mariadb:11` image.
- **PyMySQL** (pure Python) with parameterised SQL queries (`%s` placeholders).
- No ORM.

## Consequences

✅ Minimal function image (PyMySQL = pure Python, no native wheel).
✅ A single frozen table per the brief → an ORM is over-engineered.
✅ SQL queries visible and auditable in each function's `main.py`.

⚠️ No versioned migrations (acceptable for a frozen schema).
⚠️ If the schema were to evolve significantly, adding Alembic would become relevant — a decision to revisit.
