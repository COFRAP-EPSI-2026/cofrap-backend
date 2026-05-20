# Local development

## Prerequisites

- Python 3.12+
- Docker + Docker Compose
- `make` (optional — everything can be done by hand)
- `faas-cli` if you want to test against a local OpenFaaS

## Initial setup

```bash
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend

# Venv + dev dependencies (ruff, pytest, etc.)
python -m venv .venv
.venv/Scripts/Activate.ps1     # PowerShell, Windows
# source .venv/bin/activate     # bash/zsh

pip install -r requirements-dev.txt

# .env file (used by docker-compose and to run functions outside OpenFaaS)
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Start local MariaDB
docker compose up -d
```

At this point, `pytest` must pass green (36 tests).

## Running a function locally (outside OpenFaaS)

Each function is a standard FastAPI app, runnable directly:

```bash
cd functions/generate-password
# Load env vars (PowerShell)
Get-Content ../../.env | Where-Object { $_ -and !$_.StartsWith("#") } | ForEach-Object {
    $k,$v = $_ -split '=',2; Set-Item "env:$k" $v
}
# OR bash
# export $(grep -v '^#' ../../.env | xargs)

pip install -r requirements.txt
uvicorn main:app --reload --port 5001
```

Test:

```bash
curl -s -X POST http://127.0.0.1:5001/ \
     -H 'Content-Type: application/json' \
     -d '{"username":"alice"}' | jq
```

## Code conventions

- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Type hints**: preferred, but not checked in CI (no mypy/pyright configured — a deliberate choice for PoC simplicity).
- **Imports**: `from __future__ import annotations` at the top of test files to allow PEP 604 (`str | None`) without breaking evaluation hints.

The root `pyproject.toml` concentrates all the configuration (ruff, pytest, markers, line-length 100).

## Testing

See [`testing.md`](testing.md). Summary:

```bash
# Everything
pytest

# Unit only
pytest -m unit

# Integration only (requires docker compose up -d)
pytest -m integration

# A single test
pytest tests/unit/test_generate_password.py::test_password_meets_complexity -v
```

## Typical dev cycle

1. Edit `functions/<fn>/main.py` or a shared module.
2. `ruff check --fix . && ruff format .`
3. `pytest` (green?)
4. Test locally: `uvicorn main:app --reload` then curl or the [Bruno collection](../../bruno/).
5. Commit + PR. CI replays lint + tests + build of the 3 Docker images.

## Updating shared modules

`db.py`, `crypto.py` and `qr.py` are **duplicated** in each function (see [`architecture.md`](architecture.md)). If you change `crypto.py` in `functions/generate-password/`, remember to mirror it into `generate-2fa/` and `authenticate-user/`.

A custom linter or a pre-commit hook could be added to detect drift — not implemented for the PoC.

## Useful tools

- [Bruno](https://www.usebruno.com/) to test the API by hand (ready-made collection in [`bruno/`](../../bruno/)).
- [DBeaver](https://dbeaver.io/) or the `mariadb` CLI to inspect the DB:
  ```bash
  docker compose exec mariadb mariadb -ucofrap -pcofrap_dev cofrap
  ```
- [`k9s`](https://k9scli.io/) to explore the Kubernetes cluster in a TUI once OpenFaaS is deployed.

## Editor

A root `.editorconfig` fixes indentation, line endings and encoding for all compatible editors (VS Code, JetBrains, vim, etc.).

For VS Code, the recommended extensions are: Python, Pylance, Ruff, Docker, YAML.

## Common issues

See [`troubleshooting.md`](troubleshooting.md).
