<div align="center">

# cofrap-backend

**🇫🇷 Français** · [🇬🇧 English](README.en.md)

**Backend serverless du PoC COFRAP** — gestion automatisée des credentials avec mot de passe robuste, 2FA TOTP et rotation 6 mois, déployé sur OpenFaaS.

[![CI](https://github.com/COFRAP-EPSI-2026/cofrap-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/COFRAP-EPSI-2026/cofrap-backend/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenFaaS](https://img.shields.io/badge/OpenFaaS-Community-3b4cca?logo=openfaas&logoColor=white)](https://www.openfaas.com/)
[![MariaDB](https://img.shields.io/badge/MariaDB-12-003545?logo=mariadb&logoColor=white)](https://mariadb.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=COFRAP-EPSI-2026_cofrap-backend&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=COFRAP-EPSI-2026_cofrap-backend)

</div>

---

## Sommaire

- [Contexte](#contexte)
- [Architecture](#architecture)
- [Fonctions](#fonctions)
- [Démarrage rapide](#démarrage-rapide)
- [Déploiement sur Kubernetes](#déploiement-sur-kubernetes)
- [Tests](#tests)
- [CI/CD](#cicd)
- [Versioning](#versioning)
- [Structure du dépôt](#structure-du-dépôt)
- [Documentation](#documentation)
- [Contribuer](#contribuer)
- [Licence](#licence)

---

## Contexte

Réponse à la **MSPR TPRE912** (BLOC 2 — gestion d'un projet de développement serverless).

La COFRAP, suite à plusieurs compromissions de comptes liés à des mots de passe faibles et à l'absence de 2FA, a remanié son processus de création de comptes : génération automatique d'un mot de passe à 24 caractères, activation forcée du 2FA TOTP, expiration à 6 mois. Ce dépôt en est le PoC backend serverless.

Frontend TypeScript séparé · documentation détaillée dans [`docs/fr/`](docs/fr/README.md).

## Architecture

```
┌──────────────┐    HTTP/JSON     ┌────────────────────────┐    SQL    ┌──────────┐
│ Frontend TS  │ ────────────────►│    OpenFaaS Gateway    │ ─────────►│ MariaDB  │
└──────────────┘                  │  ├─ generate-password  │           └──────────┘
                                  │  ├─ generate-2fa       │
                                  │  └─ authenticate-user  │
                                  └────────────────────────┘
                                          ▲
                                          │  secrets OpenFaaS
                                          │  ├─ mariadb-password
                                          │  └─ encryption-key (Fernet)
```

**Stack** : Python 3.12 · FastAPI · Uvicorn · of-watchdog (HTTP mode) · PyMySQL · Fernet · pyotp · qrcode · slowapi (rate-limit) · MariaDB 12.

→ Détails et justifications : [`docs/fr/architecture.md`](docs/fr/architecture.md) et [`docs/fr/adr/`](docs/fr/adr/).

## Fonctions

| Fonction                                                                    | Méthode | Description                                                                            |
|-----------------------------------------------------------------------------|---------|----------------------------------------------------------------------------------------|
| [`generate-password`](functions/generate-password/main.py)                  | `POST`  | Mot de passe 24 caractères avec complexité garantie, chiffré, transmis via QR PNG      |
| [`generate-2fa`](functions/generate-2fa/main.py)                            | `POST`  | Secret TOTP base32, URI `otpauth://` + QR, chiffré en BDD                              |
| [`authenticate-user`](functions/authenticate-user/main.py)                  | `POST`  | Vérifie credentials + TOTP, contrôle l'ancienneté 6 mois, bascule `expired` si périmé |

Référence complète des payloads et codes erreur : [`docs/fr/api.md`](docs/fr/api.md).
Contrat machine-lisible : [`docs/openapi.yaml`](docs/openapi.yaml) (OpenAPI 3.1, généré depuis FastAPI).

## Démarrage rapide

> Pré-requis : Python 3.12+, Docker, `git`.

```bash
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend

# Venv + dépendances dev
python -m venv .venv
.venv/Scripts/Activate.ps1                      # bash/zsh : source .venv/bin/activate
pip install -r requirements-dev.txt

# Clé Fernet + MariaDB locale
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
docker compose up -d

# Vérifier — 36 tests verts
pytest
```

À ce stade, tout l'outillage est prêt. Pour lancer **une fonction localement hors OpenFaaS** :

```bash
cd functions/generate-password
pip install -r requirements.txt
uvicorn main:app --reload --port 5001
```

→ Tester via la [collection Bruno](bruno/) (`bruno/README.md`).

## Déploiement sur Kubernetes

Stack complète (MariaDB + OpenFaaS + 3 fonctions) en **une commande** via un chart Helm dédié.

```bash
# Linux / macOS / WSL / Git Bash
./scripts/prod/install.sh

# Windows PowerShell
./scripts/prod/install.ps1
```

Le script vérifie les prérequis (`kubectl`, `helm`), installe OpenFaaS si absent, génère les secrets (clé Fernet + mots de passe MariaDB), puis déploie le chart [`deploy/helm/cofrap`](deploy/helm/cofrap).

→ Guide détaillé (K3s, minikube Windows/Linux, cluster existant, désinstallation, troubleshooting) : [`docs/fr/installation.md`](docs/fr/installation.md).
→ Pipeline CI/CD et build d'images : [`docs/fr/deployment.md`](docs/fr/deployment.md).

## Tests

```bash
pytest                        # 36 tests (30 unitaires + 6 intégration)
pytest -m unit                # unitaires seulement (pas de Docker requis)
pytest -m integration         # intégration seulement (nécessite docker compose up -d)
pytest --cov=functions        # avec couverture
```

→ Stratégie complète : [`docs/fr/testing.md`](docs/fr/testing.md).

## CI/CD

Quatre workflows GitHub Actions :

| Workflow                                                     | Déclencheur                  | Rôle                                                                                                |
|--------------------------------------------------------------|------------------------------|-----------------------------------------------------------------------------------------------------|
| [`ci.yml`](.github/workflows/ci.yml)                         | PR vers `dev` ou `main`      | **Validation** : `ruff` + `pytest` (service MariaDB) + build des 3 images (sans push) — réutilisable via `workflow_call` |
| [`pre-release.yml`](.github/workflows/pre-release.yml)       | push sur `dev` (+ merge-group)| Rejoue `ci.yml`, puis **publie les images `:dev`** (+ `:dev-<sha>`) sur GHCR (multi-arch amd64/arm64) |
| [`release-please.yml`](.github/workflows/release-please.yml) | push sur `main`              | **Voie principale de release** : maintient la Release PR, au merge → tag `vX.Y.Z` + images `2026.X.Y` + `latest` |
| [`release.yml`](.github/workflows/release.yml)               | tag `v*.*.*` poussé à la main| Filet de secours : rejoue CI puis build/push multi-arch sur GHCR                                    |

Toutes les publications GHCR utilisent `provenance: false` (évite les entrées d'arch `unknown/unknown`). Les images sortent en multi-arch `linux/amd64,linux/arm64`. Le déploiement sur cluster reste manuel (`./scripts/prod/install.sh` ou `helm upgrade`) — choix volontaire pour le PoC.

## Versioning

Versioning **calendaire** `ANNÉE.MINEUR.CORRECTIF` — version courante : **2026.3.2**. <!-- x-release-please-version -->

Les releases sont **automatisées par [Release Please](https://github.com/googleapis/release-please)** (l'outil de Google), à partir des [Conventional Commits](https://www.conventionalcommits.org/) :

1. Tu pushes des commits `feat:` / `fix:` sur `main`.
2. Release Please ouvre/maintient une **« Release PR »** qui bumpe tous les fichiers de version + le `CHANGELOG`.
3. Tu merges cette PR → le tag `vX.Y.Z` et la GitHub Release sont créés.
4. Le workflow [`release-please.yml`](.github/workflows/release-please.yml) build et pousse les 3 images sur `ghcr.io/cofrap-epsi-2026/<function>:X.Y.Z`.

`feat:` → bump mineur (`2026.MINEUR+1.0`), `fix:` → bump correctif (`2026.x.PATCH+1`). Historique complet : [`CHANGELOG.md`](CHANGELOG.md).

> Tags manuels possibles aussi : `git tag vX.Y.Z && git push origin vX.Y.Z` déclenche [`release.yml`](.github/workflows/release.yml).

## Structure du dépôt

```
.
├── CLAUDE.md                       # Contexte projet pour Claude Code
├── README.md                       # ← vous êtes ici (FR)
├── README.en.md                     # version anglaise
├── CHANGELOG.md                     # historique des versions
├── pyproject.toml                  # Config ruff + pytest
├── requirements-dev.txt            # Dépendances dev (pytest, ruff, etc.)
├── stack.yml                       # Manifeste OpenFaaS (les 3 fonctions)
├── docker-compose.yml              # MariaDB pour dev local
├── .env.example
├── functions/
│   ├── generate-password/          # FastAPI + Dockerfile of-watchdog
│   ├── generate-2fa/
│   └── authenticate-user/
├── deploy/
│   ├── helm/cofrap/                # Chart Helm (install one-shot)
│   ├── mariadb/                    # Manifestes K8s bruts (alternative au chart)
│   ├── init.sql                    # Schéma initial
│   └── openfaas-secrets.example.sh
├── tests/
│   ├── unit/                       # Tests unitaires (BDD mockée)
│   └── integration/                # Tests d'intégration (vraie MariaDB)
├── bruno/                          # Collection API prête à l'emploi
├── docs/
│   ├── fr/                         # Documentation française
│   ├── en/                         # Documentation anglaise
│   └── openapi.yaml                # Contrat OpenAPI (neutre)
├── scripts/
│   ├── prod/                       # déploiement cluster (install / uninstall / build-images)
│   ├── dev/                        # dev local (pilotage docker-compose)
│   └── generate-openapi.py         # génération du contrat OpenAPI
└── .github/workflows/              # ci.yml · pre-release.yml (dev) · release-please.yml · release.yml
```

## Documentation

Documentation bilingue : [`docs/fr/`](docs/fr/README.md) · [`docs/en/`](docs/en/README.md).

| Document                                                | Contenu                                                          |
|---------------------------------------------------------|------------------------------------------------------------------|
| [`installation.md`](docs/fr/installation.md)            | Install pas-à-pas K3s / minikube / cluster existant, Windows + Linux |
| [`architecture.md`](docs/fr/architecture.md)            | Vue d'ensemble, choix techniques, flux end-to-end                |
| [`api.md`](docs/fr/api.md)                              | Référence API : payloads, codes erreur, exemples curl            |
| [`openapi.yaml`](docs/openapi.yaml)                     | Contrat machine-lisible (OpenAPI 3.1) — généré depuis FastAPI    |
| [`deployment.md`](docs/fr/deployment.md)                | Procédure complète Kubernetes + OpenFaaS + MariaDB               |
| [`security.md`](docs/fr/security.md)                    | Modèle de menace, chiffrement, rotation, secrets                 |
| [`development.md`](docs/fr/development.md)              | Setup local, conventions, cycle de dev                           |
| [`testing.md`](docs/fr/testing.md)                      | Stratégie de tests, exécution, fixtures                          |
| [`troubleshooting.md`](docs/fr/troubleshooting.md)      | Erreurs fréquentes et résolutions                                |
| [`adr/`](docs/fr/adr/)                                  | Architecture Decision Records — choix structurants justifiés     |

## Contribuer

1. Fork + branche feature.
2. `pip install -r requirements-dev.txt`, `docker compose up -d`.
3. Code + `ruff check --fix . && ruff format .` + `pytest`.
4. PR vers `main`. La CI rejoue lint + tests + build.

Conventions de commit : style Conventional Commits encouragé (`feat:`, `fix:`, `docs:`, etc.) mais non bloquant pour ce PoC.

## Licence

[MIT](LICENSE) © 2026 COFRAP-EPSI-2026.

---

<div align="center">
<sub>Réalisé dans le cadre de la MSPR TPRE912 — EPSI / Pro Alterna · Bloc 2 — Manager un projet informatique avec agilité.</sub>
</div>
