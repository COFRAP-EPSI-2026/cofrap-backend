# Changelog

Toutes les évolutions notables du backend COFRAP. / All notable changes to the COFRAP backend.

Format inspiré de [Keep a Changelog](https://keepachangelog.com/).

## Schéma de version / Versioning scheme

Le projet utilise un versioning **calendaire** : `ANNÉE.MINEUR.CORRECTIF` (`YYYY.MINOR.PATCH`).

- `YYYY` — année de la release (`2026`).
- `MINOR` — incrémenté à chaque lot de fonctionnalités.
- `PATCH` — incrémenté pour les corrections sans nouvelle fonctionnalité.

Une release se déclenche en poussant un **tag git `vYYYY.MINOR.PATCH`** (ex. `v2026.1.0`). Le workflow [`release.yml`](.github/workflows/release.yml) rejoue la CI, build les 3 images multi-arch et les pousse sur `ghcr.io/cofrap-epsi-2026/<function>:<version>`.

La même version est portée par : `pyproject.toml`, `deploy/helm/cofrap/Chart.yaml` (`version` + `appVersion`), `deploy/helm/cofrap/values.yaml` (`functions.version`), `stack.yml`, les apps FastAPI (`functions/*/main.py`) et `docs/openapi.yaml`. Tout bump doit les mettre à jour ensemble.

---

## [2026.2.0](https://github.com/COFRAP-EPSI-2026/cofrap-backend/compare/v2026.1.2...v2026.2.0) (2026-05-20)


### Features

* ajout de la prise en charge de Release Please pour l'automatisation des versions et mise à jour de la version à 2026.1.2 dans tous les fichiers pertinents ([734f9b3](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/734f9b3ba1cefa86391decf32557c74535107592))

## [2026.1.2] — 2026-05-20

Aucun changement du schéma BDD. Le contrat d'API est inchangé ; seuls des en-têtes CORS sont ajoutés aux réponses.

### Ajouté / Added

- Middleware CORS sur les 3 fonctions (`CORSMiddleware` FastAPI) — permet au frontend, servi depuis une autre origine, d'appeler l'API depuis le navigateur. Origines configurables via la variable d'environnement `CORS_ALLOW_ORIGINS` (`*` par défaut, ou liste séparée par virgules). Câblé dans `stack.yml`, le chart Helm (`functions.corsAllowOrigins`) et `.env.example`.
- 9 tests CORS (`tests/unit/test_cors.py`) : préflight OPTIONS, en-tête sur requête simple, restriction par liste explicite.

## [2026.1.1] — 2026-05-20

Version de maintenance — alignement des versions et du registre d'images.

### Corrigé / Fixed

- Harmonisation du registre d'images sur `ghcr.io/cofrap-epsi-2026` dans tous les manifestes (`stack.yml` alignait encore l'ancien préfixe `ghcr.io/cofrap`).
- Cohérence de version : toutes les sources (`pyproject.toml`, chart Helm, `stack.yml`, apps FastAPI, scripts, `docs/openapi.yaml`) portent désormais la même valeur.

## [2026.1.0] — 2026-05-20

Première release du PoC backend serverless COFRAP (MSPR TPRE912).

### Ajouté / Added

- 3 fonctions OpenFaaS Python/FastAPI : `generate-password`, `generate-2fa`, `authenticate-user`.
- Génération de mot de passe 24 caractères (4 classes, CSPRNG), chiffrement Fernet, QR code PNG.
- Secret TOTP (RFC 6238) avec URI `otpauth://` et QR code.
- Authentification avec contrôle d'expiration à 6 mois et bascule `expired`.
- Base MariaDB 11 (StatefulSet K8s + `docker-compose.yml` pour le dev local).
- Chart Helm unique [`deploy/helm/cofrap`](deploy/helm/cofrap) : MariaDB + secrets + Deployments des 3 fonctions.
- Scripts d'installation reproductibles Linux/Windows (`install.sh`/`.ps1`, `uninstall`, `build-images`).
- Suite de tests : 30 unitaires + 6 d'intégration (pytest).
- CI/CD GitHub Actions : `ci.yml` (lint + tests + build) et `release.yml` (build multi-arch + push GHCR sur tag).
- Collection Bruno prête à l'emploi (3 environnements).
- Contrat OpenAPI 3.1 généré depuis FastAPI (`docs/openapi.yaml`).
- Documentation bilingue FR/EN dans `docs/fr/` et `docs/en/`.

### Notes

- Déploiement compatible **OpenFaaS Community** : les fonctions sont des `Deployment` + `Service` labellisés `faas_function=<name>` (l'operator CRD est réservé à OpenFaaS Pro).
- Le déploiement sur cluster reste manuel (`./scripts/install.sh` ou `helm upgrade`) — pas de CD automatique dans cette version.

[2026.1.2]: https://github.com/COFRAP-EPSI-2026/cofrap-backend/releases/tag/v2026.1.2
[2026.1.1]: https://github.com/COFRAP-EPSI-2026/cofrap-backend/releases/tag/v2026.1.1
[2026.1.0]: https://github.com/COFRAP-EPSI-2026/cofrap-backend/releases/tag/v2026.1.0
