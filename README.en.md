<div align="center">

# cofrap-backend

[🇫🇷 Français](README.md) · **🇬🇧 English**

**Serverless backend of the COFRAP PoC** — automated credential management with a strong password, TOTP 2FA and 6-month rotation, deployed on OpenFaaS.

[![CI](https://github.com/COFRAP-EPSI-2026/cofrap-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/COFRAP-EPSI-2026/cofrap-backend/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenFaaS](https://img.shields.io/badge/OpenFaaS-Community-3b4cca?logo=openfaas&logoColor=white)](https://www.openfaas.com/)
[![MariaDB](https://img.shields.io/badge/MariaDB-11-003545?logo=mariadb&logoColor=white)](https://mariadb.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

</div>

---

## Table of contents

- [Context](#context)
- [Architecture](#architecture)
- [Functions](#functions)
- [Quick start](#quick-start)
- [Deploying to Kubernetes](#deploying-to-kubernetes)
- [Tests](#tests)
- [CI/CD](#cicd)
- [Versioning](#versioning)
- [Repository layout](#repository-layout)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Context

Answer to the **MSPR TPRE912** (BLOCK 2 — managing a serverless development project).

Following several account compromises caused by weak passwords and the absence of 2FA, COFRAP reworked its account-creation process: automatic generation of a 24-character password, mandatory TOTP 2FA activation, 6-month expiry. This repository is the serverless backend PoC for it.

TypeScript frontend in a separate repo · detailed documentation in [`docs/en/`](docs/en/README.md).

## Architecture

```
┌──────────────┐    HTTP/JSON     ┌────────────────────────┐    SQL    ┌──────────┐
│ Frontend TS  │ ────────────────►│    OpenFaaS Gateway    │ ─────────►│ MariaDB  │
└──────────────┘                  │  ├─ generate-password  │           └──────────┘
                                  │  ├─ generate-2fa       │
                                  │  └─ authenticate-user  │
                                  └────────────────────────┘
                                          ▲
                                          │  OpenFaaS secrets
                                          │  ├─ mariadb-password
                                          │  └─ encryption-key (Fernet)
```

**Stack**: Python 3.12 · FastAPI · Uvicorn · of-watchdog (HTTP mode) · PyMySQL · Fernet · pyotp · qrcode · MariaDB 11.

→ Details and rationale: [`docs/en/architecture.md`](docs/en/architecture.md) and [`docs/en/adr/`](docs/en/adr/).

## Functions

| Function                                                                    | Method | Description                                                                        |
|-----------------------------------------------------------------------------|--------|-------------------------------------------------------------------------------------|
| [`generate-password`](functions/generate-password/main.py)                  | `POST` | 24-character password with guaranteed complexity, encrypted, transmitted via PNG QR |
| [`generate-2fa`](functions/generate-2fa/main.py)                            | `POST` | base32 TOTP secret, `otpauth://` URI + QR, encrypted in the DB                      |
| [`authenticate-user`](functions/authenticate-user/main.py)                  | `POST` | Verifies credentials + TOTP, checks the 6-month age, flips `expired` if stale       |

Full reference of payloads and error codes: [`docs/en/api.md`](docs/en/api.md).
Machine-readable contract: [`docs/openapi.yaml`](docs/openapi.yaml) (OpenAPI 3.1, generated from FastAPI).

## Quick start

> Prerequisites: Python 3.12+, Docker, `git`.

```bash
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend

# Venv + dev dependencies
python -m venv .venv
.venv/Scripts/Activate.ps1                      # bash/zsh: source .venv/bin/activate
pip install -r requirements-dev.txt

# Fernet key + local MariaDB
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
docker compose up -d

# Verify — 36 green tests
pytest
```

At this point the whole toolchain is ready. To run **a function locally outside OpenFaaS**:

```bash
cd functions/generate-password
pip install -r requirements.txt
uvicorn main:app --reload --port 5001
```

→ Test it with the [Bruno collection](bruno/) (`bruno/README.md`).

## Deploying to Kubernetes

The full stack (MariaDB + OpenFaaS + 3 functions) in **one command** via a dedicated Helm chart.

```bash
# Linux / macOS / WSL / Git Bash
./scripts/install.sh

# Windows PowerShell
./scripts/install.ps1
```

The script checks the prerequisites (`kubectl`, `helm`), installs OpenFaaS if absent, generates the secrets (Fernet key + MariaDB passwords), then deploys the [`deploy/helm/cofrap`](deploy/helm/cofrap) chart.

→ Detailed guide (K3s, minikube Windows/Linux, existing cluster, uninstall, troubleshooting): [`docs/en/installation.md`](docs/en/installation.md).
→ CI/CD pipeline and image build: [`docs/en/deployment.md`](docs/en/deployment.md).

## Tests

```bash
pytest                        # 36 tests (30 unit + 6 integration)
pytest -m unit                # unit only (no Docker required)
pytest -m integration         # integration only (requires docker compose up -d)
pytest --cov=functions        # with coverage
```

→ Full strategy: [`docs/en/testing.md`](docs/en/testing.md).

## CI/CD

Two GitHub Actions workflows:

- [`ci.yml`](.github/workflows/ci.yml) — on PR and push to `main`: `ruff` + `pytest` (with a MariaDB service) + build of the 3 Docker images.
- [`release.yml`](.github/workflows/release.yml) — on a `v*.*.*` tag: replays CI then **multi-arch build (amd64/arm64) + push to GHCR** of the 3 functions, with SBOM and provenance attestation.

Deployment stays manual (`faas-cli up` / `helm`) — a deliberate choice for the PoC.

## Versioning

**Calendar** versioning `YEAR.MINOR.PATCH` — current version: **2026.1.0**.

A release is triggered by pushing a git tag `vYYYY.MINOR.PATCH`:

```bash
git tag v2026.1.0 && git push origin v2026.1.0
```

The `release.yml` workflow replays CI then builds and pushes the 3 images to `ghcr.io/cofrap-epsi-2026/<function>:2026.1.0`. Full history: [`CHANGELOG.md`](CHANGELOG.md).

## Repository layout

```
.
├── CLAUDE.md                       # Project context for Claude Code
├── README.md                       # French version
├── README.en.md                     # ← you are here (EN)
├── CHANGELOG.md                     # version history
├── pyproject.toml                  # ruff + pytest config
├── requirements-dev.txt            # Dev dependencies (pytest, ruff, etc.)
├── stack.yml                       # OpenFaaS manifest (the 3 functions)
├── docker-compose.yml              # MariaDB for local dev
├── .env.example
├── functions/
│   ├── generate-password/          # FastAPI + of-watchdog Dockerfile
│   ├── generate-2fa/
│   └── authenticate-user/
├── deploy/
│   ├── helm/cofrap/                # Helm chart (one-shot install)
│   ├── mariadb/                    # Raw K8s manifests (chart alternative)
│   ├── init.sql                    # Initial schema
│   └── openfaas-secrets.example.sh
├── tests/
│   ├── unit/                       # Unit tests (mocked DB)
│   └── integration/                # Integration tests (real MariaDB)
├── bruno/                          # Ready-to-use API collection
├── docs/
│   ├── fr/                         # French documentation
│   ├── en/                         # English documentation
│   └── openapi.yaml                # OpenAPI contract (language-neutral)
├── scripts/                        # install / build-images / generate-openapi
└── .github/workflows/              # CI + Release
```

## Documentation

Bilingual documentation: [`docs/fr/`](docs/fr/README.md) · [`docs/en/`](docs/en/README.md).

| Document                                                | Content                                                          |
|---------------------------------------------------------|------------------------------------------------------------------|
| [`installation.md`](docs/en/installation.md)            | Step-by-step install on K3s / minikube / existing cluster, Windows + Linux |
| [`architecture.md`](docs/en/architecture.md)            | Overview, technical choices, end-to-end flow                     |
| [`api.md`](docs/en/api.md)                              | API reference: payloads, error codes, curl examples              |
| [`openapi.yaml`](docs/openapi.yaml)                     | Machine-readable contract (OpenAPI 3.1) — generated from FastAPI |
| [`deployment.md`](docs/en/deployment.md)                | Full Kubernetes + OpenFaaS + MariaDB procedure                   |
| [`security.md`](docs/en/security.md)                    | Threat model, encryption, rotation, secrets                      |
| [`development.md`](docs/en/development.md)              | Local setup, conventions, dev cycle                              |
| [`testing.md`](docs/en/testing.md)                      | Testing strategy, execution, fixtures                            |
| [`troubleshooting.md`](docs/en/troubleshooting.md)      | Common errors and fixes                                          |
| [`adr/`](docs/en/adr/)                                  | Architecture Decision Records — justified structural choices     |

## Contributing

1. Fork + feature branch.
2. `pip install -r requirements-dev.txt`, `docker compose up -d`.
3. Code + `ruff check --fix . && ruff format .` + `pytest`.
4. PR to `main`. CI replays lint + tests + build.

Commit conventions: Conventional Commits style encouraged (`feat:`, `fix:`, `docs:`, etc.) but not enforced for this PoC.

## License

[MIT](LICENSE) © 2026 COFRAP-EPSI-2026.

---

<div align="center">
<sub>Built as part of the MSPR TPRE912 — EPSI / Pro Alterna · Block 2 — Managing an IT project with agility.</sub>
</div>
