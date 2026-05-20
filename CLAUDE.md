# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Vue d'ensemble

PoC **backend serverless** demandé par la COFRAP dans la MSPR TPRE912. Trois fonctions OpenFaaS Python/FastAPI + MariaDB. Frontend TypeScript dans un dépôt séparé.

Le `README.md` (FR) et `README.en.md` (EN) racine sont la porte d'entrée utilisateur. La documentation détaillée est **bilingue** : `docs/fr/` et `docs/en/` (contenu en miroir). Cette page (`CLAUDE.md`) ne répète pas le README — elle pointe vers ce que Claude doit savoir pour bouger vite.

## Stack et architecture

- **Python 3.12** + **FastAPI** + Uvicorn (ASGI), exécuté par **of-watchdog** en mode HTTP.
- **OpenFaaS Community** sur Kubernetes (recommandé K3S, ou minikube en repli).
- **MariaDB 11** (StatefulSet K8s + `docker-compose.yml` pour dev local).
- Driver Python : **PyMySQL** (pure Python, pas d'extension native).
- Chiffrement applicatif : **Fernet** (`cryptography`) sur les champs `password` et `mfa` en BDD.
- 2FA : **pyotp** (RFC 6238), QR code via **qrcode** + PIL.

Architecture complète : [`docs/fr/architecture.md`](docs/fr/architecture.md). Justifications : [`docs/fr/adr/`](docs/fr/adr/).

## Structure du dépôt (résumé)

```
functions/<name>/      # 3 fonctions, chacune autonome (Dockerfile, main.py, db.py, crypto.py, qr.py)
deploy/
  helm/cofrap/         # CHART HELM unique (MariaDB + secrets + Deployments des 3 fonctions) — voie principale
  mariadb/             # manifestes K8s bruts (alternative kubectl apply)
  init.sql, openfaas-secrets.example.sh
tests/unit/            # pytest avec mock pymysql
tests/integration/     # pytest avec MariaDB réelle (docker-compose / service GHA)
bruno/                 # collection Bruno prête à l'emploi (envs + flux nominal + cas d'erreur)
docs/
  fr/ , en/            # doc bilingue EN MIROIR (installation, architecture, api, deployment, security, dev, testing, troubleshooting, adr/)
  openapi.yaml         # contrat OpenAPI 3.1 (neutre, à la racine de docs/)
scripts/               # install / uninstall / build-images (.sh + .ps1) + generate-openapi.py
.github/workflows/     # ci.yml (PR + push main) + release.yml (sur tag v*)
stack.yml              # manifeste OpenFaaS (alternative au chart, pour `faas-cli up`)
docker-compose.yml     # MariaDB pour dev local
pyproject.toml         # ruff + pytest config (line-length 100, target py312)
requirements-dev.txt   # pytest, ruff, pyyaml, deps applicatives pour pouvoir lancer les tests
```

## Commandes courantes

### Setup unique

```bash
python -m venv .venv
.venv/Scripts/Activate.ps1                                # PowerShell
# source .venv/bin/activate                               # bash/zsh
pip install -r requirements-dev.txt
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
docker compose up -d
```

### Lint + format

```bash
ruff check .             # lint
ruff check --fix .       # auto-fix
ruff format .            # formatage
ruff format --check .    # vérification CI-style (sans modifier)
```

### Tests

```bash
pytest                                  # tout (36 tests : 30 unit + 6 integration)
pytest -m unit                          # unitaires seulement
pytest -m integration                   # intégration seulement (nécessite docker compose up)
pytest tests/unit/test_<x>.py::<test> -v   # un seul test
pytest --cov=functions --cov-report=term-missing
```

Les tests d'intégration sont **auto-skippés** si MariaDB n'est pas joignable (`tests/integration/conftest.py:_is_mariadb_reachable`). Pas besoin de `-m unit` pour éviter de les voir échouer.

### OpenFaaS

```bash
faas-cli login -g $OPENFAAS_URL -u admin --password-stdin <<< $OF_PASSWORD
faas-cli up -f stack.yml                            # build + push + deploy les 3 fonctions
faas-cli up --filter generate-password -f stack.yml # une seule
faas-cli invoke generate-password                   # test d'invocation
faas-cli secret list
```

### Déploiement complet (chart Helm)

```bash
./scripts/install.sh             # Linux / WSL / Git Bash
./scripts/install.ps1            # Windows PowerShell
./scripts/uninstall.sh           # nettoyage
```

Voir [`docs/fr/installation.md`](docs/fr/installation.md) pour les variantes K3s / minikube / cluster existant. Le chart vit dans [`deploy/helm/cofrap/`](deploy/helm/cofrap/). Pour valider sans appliquer : `helm lint deploy/helm/cofrap && helm template cofrap deploy/helm/cofrap --set secrets.encryptionKey=x --set secrets.mariadbPassword=x --set secrets.mariadbRootPassword=x`.

### API spec (OpenAPI)

```bash
python scripts/generate-openapi.py    # → docs/openapi.yaml
```

À relancer **dès qu'un `main.py` ou un modèle Pydantic est modifié** — sinon `docs/openapi.yaml` drift par rapport au code. Le fichier est commité (pas un artefact CI) pour qu'il soit consultable directement dans le dépôt.

## Spécification métier (rappel — à respecter strictement)

- Mot de passe **24 caractères**, 4 classes (majuscules, minuscules, chiffres, spéciaux).
- Chiffrement obligatoire des champs `password` et `mfa` (Fernet, clé via secret OpenFaaS `encryption-key`).
- QR code à **usage unique** pour la transmission du mot de passe en clair — ne jamais le logger.
- **Rotation à 6 mois** : vérification dans `authenticate-user` (pas de cron). Bascule `expired = 1` et renvoie `action: regenerate_password_and_2fa`.
- `generate-2fa` fait un `UPDATE`, pas un `INSERT` → 404 si l'utilisateur n'existe pas.
- Schéma BDD figé (table `users` à 6 colonnes : `id`, `username`, `password`, `mfa`, `gendate`, `expired`). Pas de colonnes additionnelles sans bonne raison.

## Conventions critiques pour Claude

- **Modules partagés dupliqués** : `db.py`, `crypto.py`, `qr.py` existent en copie dans chaque fonction. Si tu modifies l'un, répercute dans les **3** dossiers (`generate-password`, `generate-2fa`, `authenticate-user`). Justification : [`docs/fr/adr/0006-duplicate-shared-utilities.md`](docs/fr/adr/0006-duplicate-shared-utilities.md).
- **Documentation bilingue en miroir** : toute modif d'un fichier `docs/fr/<x>.md` doit être répercutée dans `docs/en/<x>.md` (et inversement). Les deux arbres ont la même structure. `docs/openapi.yaml` est neutre (généré, pas de version par langue).
- **Déploiement = Deployments K8s, pas CRD `Function`** : OpenFaaS Community ne supporte pas l'operator (réservé Pro). Le chart crée des `Deployment` + `Service` labellisés `faas_function=<name>` dans `openfaas-fn`. Ne pas réintroduire de CRD `openfaas.com/v1`.
- **Fallback env vars** : `_read_secret(name)` lit `/var/openfaas/secrets/<name>` en prod, fallback sur la variable d'env `<NAME_UPPER_SNAKE>` pour dev/CI. Quand tu ajoutes un nouveau secret, suis le même pattern.
- **Tests d'intégration** = MariaDB **réelle** (pas de mock). Si tu changes une requête SQL, le test d'intégration doit la valider. Voir `tests/integration/test_full_flow.py`.
- **Format des réponses d'erreur** : utiliser `HTTPException(status_code=…, detail="…")` avec un message en anglais lowercase (`"invalid credentials"`, `"invalid otp"`, `"user not found"`). Plusieurs tests asserent sur ces strings.
- **`response_model` Pydantic** : les handlers utilisent des modèles de réponse explicites pour enrichir l'OpenAPI. Le handler `authenticate-user` utilise `response_model_exclude_none=True` parce que ses champs `username` et `action` sont conditionnels. Préserve cette config en l'étendant.
- **`pyproject.toml`** : la ligne `line-length` est à **100**, pas 88 (défaut ruff). Penser à `ruff format` avant de commit.
- **Markers pytest stricts** : tout test doit être annoté `pytestmark = pytest.mark.unit` ou `integration` (le strict est activé dans `pyproject.toml`).
- **Bruno : URL par fonction** : les requêtes utilisent `{{generate_password_url}}` / `{{generate_2fa_url}}` / `{{authenticate_user_url}}` (pas un seul `{{gateway}}`). Cela permet de switcher entre mode direct uvicorn (3 ports) et mode OpenFaaS gateway (1 URL avec `/function/<name>`) en changeant juste d'environnement.
- **Chart Helm = source de vérité du déploiement** : si tu modifies un manifeste K8s (image registry, secrets attendus par les fonctions, schéma BDD, etc.), modifie dans `deploy/helm/cofrap/templates/` en priorité. Les manifestes bruts dans `deploy/mariadb/` sont une alternative pédagogique conservée pour la lecture — ils peuvent diverger sans casser la CI.

## CI/CD

- [`ci.yml`](.github/workflows/ci.yml) : `ruff` + `pytest` (avec service MariaDB 11) + build des 3 images Docker (sans push). Réutilisable via `workflow_call` par `release.yml`.
- [`release.yml`](.github/workflows/release.yml) : sur tag `v*.*.*`, rejoue le CI puis matrix sur les 3 fonctions → build multi-arch amd64/arm64 + push sur `ghcr.io/<org>/<function>:<version>` avec `provenance: true` et `sbom: true`.

Le déploiement sur cluster est **manuel** (`faas-cli up`) — pas de CD automatique.

## Quand tu finis quelque chose

Si tu ajoutes/modifies du code applicatif :

1. `ruff check --fix . && ruff format .`
2. `pytest` doit passer (les 36 tests existants + tes nouveaux)
3. Si tu as touché un `main.py` ou un modèle Pydantic : `python scripts/generate-openapi.py` pour rafraîchir `docs/openapi.yaml`.
4. Si tu touches une fonction, vérifier que la documentation correspondante reste à jour, **dans les deux langues** : `docs/{fr,en}/api.md` (payload/erreurs), `docs/{fr,en}/architecture.md` (si flux modifié), `docs/{fr,en}/security.md` (si traitement des secrets modifié).
5. Si tu ajoutes un nouveau choix structurant, ajouter une ADR dans `docs/fr/adr/` **et** `docs/en/adr/`.
6. Pas de README/docs autogénérés sans demande explicite — le PoC veut rester lisible et concis.
