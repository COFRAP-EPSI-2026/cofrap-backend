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

## [2026.5.0](https://github.com/COFRAP-EPSI-2026/cofrap-backend/compare/v2026.4.0...v2026.5.0) (2026-05-28)


### Features

* Ajouter la gestion des secrets pour OpenFaaS et MariaDB dans les valeurs Helm ([a72fd2e](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/a72fd2eb9c4c6e7657f6ad54429640e0d3e4a2bf))

## [2026.4.0](https://github.com/COFRAP-EPSI-2026/cofrap-backend/compare/v2026.3.2...v2026.4.0) (2026-05-25)


### Features

* ajouter des scans de sécurité avec Bandit et Gitleaks, et configurer les mises à jour automatiques des dépendances ([f3076d7](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/f3076d764b2bcbc4a4195f10d4135df601bf7750))
* ajouter la configuration de CloudBeaver et le mot de passe admin dans .env.example ([8a3733f](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/8a3733f3122e8fa785d057d3ca8cfe2c989ec8c1))
* ajouter la configuration SonarQube et les rapports de linting, mise à jour des dépendances et ajustements dans les fichiers de configuration ([7558220](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/75582209f6d44d59412998f2b4463c0c08dd1eb3))
* ajouter la variable d'environnement GITLEAKS_LICENSE pour Gitleaks ([faca658](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/faca658809e15625df993497fcdd60c484c0d7b7))
* ajouter la variable d'environnement GITLEAKS_LICENSE pour Gitleaks ([607ef34](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/607ef34efcfb1be8c62a9ba70ac7f0b5875bbbf0))
* améliorer l'analyse SonarCloud avec des rapports de linting et suppression de l'ancien workflow SonarQube ([97cace9](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/97cace98f49337d99d7454cef734f026a70ddacb))
* mettre à jour l'action SonarQube et le checkout dans le workflow CI ([0c6c125](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/0c6c12593986f7287d41e22e2e3266cc527432fc))
* mettre à jour la configuration de CloudBeaver avec un nouveau fichier de configuration et ajouter les sources de données ([23f9c19](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/23f9c19aaff6ac48252071f3ac3439b5613e061e))
* mettre à jour la configuration SonarQube avec la clé de projet et l'organisation ([411f790](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/411f7909d6f28c2299afc9c4f8c4246718050189))
* mettre à jour les images de MariaDB et Traefik dans le fichier docker-compose ([cbce183](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/cbce18338d711760516e48c815c8ed3b308c3ed7))
* Refactor installation and uninstallation scripts for COFRAP stack ([8f28388](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/8f28388cb1a735ae6ec7f17780495398a1163a01))
* remplacer Gitleaks par TruffleHog dans l'analyse de sécurité et mettre à jour phpMyAdmin vers CloudBeaver ([b0fdc8d](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/b0fdc8dd82ba5f7eb1af8b6faaebcf3efd3a0b55))
* remplacer la configuration Bandit par un fichier YAML et mettre à jour le chemin d'accès dans le workflow CI ([b043cb3](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/b043cb3f198b11b2f0cefc7bfb308bbb11bd376b))


### Bug Fixes

* ajouter l'héritage des secrets dans les jobs de validation des workflows pre-release et release ([9eeff87](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/9eeff87812bbf5715aa1351cefd9b4ac8bb42bd2))
* ajouter les variables d'environnement GITHUB_TOKEN et SONAR_TOKEN dans les sections env des workflows pre-release et release ([5d79c6b](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/5d79c6bd2b14d84d54c9bec808e91203041d2f62))
* commenter la version du projet dans la configuration SonarQube ([ac67074](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/ac6707406f4137065ac3ad27c948d131beccfe37))
* corriger la gestion du code de sortie dans l'analyse SonarCloud et mettre à jour l'image de Traefik ([5fba028](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/5fba0283e560515e5b4348921cf69e8beeae4eb8))
* déplacer les variables d'environnement GITHUB_TOKEN et SONAR_TOKEN dans la section env ([cec321c](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/cec321c3cf170d45b76f4cb812f6041141c3802d))
* mettre à jour la configuration de CloudBeaver en remplaçant le fichier initial-data-sources.conf par initial-data-sources.json ([967486d](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/967486dec075cecc4a94a777df1bd619b420146b))
* mettre à jour la variable d'environnement GITHUB_TOKEN pour Gitleaks ([d59ab5b](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/d59ab5b527a68f5bb92e53f343658d956519d0cd))
* mettre à jour la version du tag à 'latest' dans les scripts de construction d'images ([577122c](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/577122c233188861358369d4e1807287555220f0))

## [2026.3.2](https://github.com/COFRAP-EPSI-2026/cofrap-backend/compare/v2026.3.1...v2026.3.2) (2026-05-21)


### Bug Fixes

* corriger le secret utilisé pour l'authentification au registre GHCR ([25e6952](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/25e6952da1b590390980020fe50504155077b2ef))

## [2026.3.1](https://github.com/COFRAP-EPSI-2026/cofrap-backend/compare/v2026.3.0...v2026.3.1) (2026-05-21)


### Bug Fixes

* corriger le secret utilisé pour l'authentification au registre GHCR ([25e6952](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/25e6952da1b590390980020fe50504155077b2ef))

## [2026.3.0](https://github.com/COFRAP-EPSI-2026/cofrap-backend/compare/v2026.2.0...v2026.3.0) (2026-05-21)


### Features

* ajouter la configuration Nginx et les services de génération de mots de passe et d'authentification ([a058ae3](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/a058ae3ff078e6b669886e7f48ed080b7b38b7c7))
* refactor la stack de développement avec Traefik et mise à jour des configurations ([50d4dcd](https://github.com/COFRAP-EPSI-2026/cofrap-backend/commit/50d4dcdeb6ae27541e4217fd79b363ef1ea51a47))

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
