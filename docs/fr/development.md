# Développement local

## Pré-requis

- Python 3.12+
- Docker + Docker Compose
- `make` (facultatif — tout est faisable à la main)
- `faas-cli` si vous voulez tester via OpenFaaS local

## Setup initial

```bash
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend

# Venv + dépendances dev (ruff, pytest, etc.)
python -m venv .venv
.venv/Scripts/Activate.ps1     # PowerShell, Windows
# source .venv/bin/activate     # bash/zsh

pip install -r requirements-dev.txt

# Fichier .env (utilisé par docker-compose et pour exécuter les fonctions hors OpenFaaS)
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Démarrer MariaDB (suffisant pour lancer pytest)
docker compose up -d mariadb
```

À ce stade, `pytest` doit passer en vert (36 tests).

## Lancer une fonction localement (hors OpenFaaS)

Chaque fonction est une app FastAPI standard, exécutable directement :

```bash
cd functions/generate-password
# Charger les vars d'env (PowerShell)
Get-Content ../../.env | Where-Object { $_ -and !$_.StartsWith("#") } | ForEach-Object {
    $k,$v = $_ -split '=',2; Set-Item "env:$k" $v
}
# OU bash
# export $(grep -v '^#' ../../.env | xargs)

pip install -r requirements.txt
uvicorn main:app --reload --port 5001
```

Test :

```bash
curl -s -X POST http://127.0.0.1:5001/ \
     -H 'Content-Type: application/json' \
     -d '{"username":"alice"}' | jq
```

## Stack complète avec docker-compose (Traefik)

`docker compose up -d --build` démarre la **stack complète** de dev : MariaDB, les
3 fonctions buildées et un reverse-proxy **Traefik** qui imite le gateway OpenFaaS.

```bash
docker compose up -d --build
```

| Service             | Port hôte | Rôle                                                    |
|---------------------|-----------|---------------------------------------------------------|
| Traefik             | `8080`    | Gateway — route `/function/<name>` vers chaque fonction |
| Traefik (dashboard) | `8090`    | <http://localhost:8090/dashboard/> — routes découvertes |
| phpMyAdmin          | `8082`    | Inspection de la BDD                                    |
| MariaDB             | `3306`    | Base de données                                         |

Les fonctions répondent alors exactement comme derrière le gateway OpenFaaS :

```bash
curl -s -X POST http://localhost:8080/function/generate-password \
     -H 'Content-Type: application/json' \
     -d '{"username":"alice"}' | jq
```

C'est le format d'URL attendu par le **frontend** (proxy `/api` de Vite) et par
l'environnement Bruno « Local OpenFaaS Gateway » — pratique pour tester
l'ensemble frontend + backend sans cluster Kubernetes.

Prérequis : `.env` doit contenir une `ENCRYPTION_KEY` valide (générée au setup
ci-dessus) ; sinon `docker compose up` s'arrête avec un message explicite.

Arrêt : `docker compose down` (`-v` pour aussi supprimer le volume MariaDB).

## Convention de code

- **Lint** : `ruff check .`
- **Format** : `ruff format .`
- **Type hints** : à privilégier, mais pas vérifiés en CI (pas de mypy/pyright configuré — choix volontaire pour la simplicité du PoC).
- **Imports** : `from __future__ import annotations` en tête des fichiers de tests pour autoriser le PEP 604 (`str | None`) sans casser les hints d'évaluation.

`pyproject.toml` à la racine concentre toute la configuration (ruff, pytest, markers, line-length 100).

## Tester

Voir [`testing.md`](testing.md). Résumé :

```bash
# Tout
pytest

# Unitaires seulement
pytest -m unit

# Intégration seulement (nécessite MariaDB : docker compose up -d mariadb)
pytest -m integration

# Un seul test
pytest tests/unit/test_generate_password.py::test_password_meets_complexity -v
```

## Cycle de dev typique

1. Modifier `functions/<fn>/main.py` ou un module partagé.
2. `ruff check --fix . && ruff format .`
3. `pytest` (vert ?)
4. Tester en local : `uvicorn main:app --reload` puis curl ou la [collection Bruno](../../bruno/).
5. Push sur `dev` (ou PR). La CI valide automatiquement — cf. ci-dessous.

## Intégration continue et releases

Trois workflows GitHub Actions, faciles à suivre :

| Workflow | Déclencheur | Rôle |
|----------|-------------|------|
| `ci.yml` | PR vers `dev` ou `main` | **Validation** : `ruff` + `pytest` + build des 3 images (sans push) |
| `pre-release.yml` | push sur `dev` | Rejoue `ci.yml` ; si vert, **publie les images `:dev`** (+ `:dev-<sha>`) sur GHCR |
| `release-please.yml` | push sur `main` | **Release stable** : Release PR → merge → tag `vX.Y.Z` + images `2026.X.Y` + `latest` |

Versionnement **calendaire** automatisé par Release Please (`feat:` → bump mineur, `fix:` → correctif) — ne jamais bumper la version à la main (cf. [`CLAUDE.md`](../../CLAUDE.md)). Le déploiement sur cluster reste manuel : [`scripts/prod/install.sh`](../../scripts/prod/install.sh) ou `helm`.

## Mettre à jour les modules partagés

`db.py`, `crypto.py` et `qr.py` sont **dupliqués** dans chaque fonction (cf. [`architecture.md`](architecture.md)). Si vous modifiez `crypto.py` dans `functions/generate-password/`, n'oubliez pas de répercuter dans `generate-2fa/` et `authenticate-user/`.

Un linter custom ou un pre-commit hook peut être ajouté pour détecter le drift — non implémenté pour le PoC.

## Outils utiles

- [Bruno](https://www.usebruno.com/) pour tester l'API à la main (collection prête dans [`bruno/`](../../bruno/)).
- [DBeaver](https://dbeaver.io/) ou la CLI `mariadb` pour inspecter la BDD :
  ```bash
  docker compose exec mariadb mariadb -ucofrap -pcofrap_dev cofrap
  ```
- [`k9s`](https://k9scli.io/) pour explorer le cluster Kubernetes en TUI une fois OpenFaaS déployé.

## Editor

Un `.editorconfig` à la racine fixe indentation, fin de ligne et encoding pour tous les éditeurs compatibles (VS Code, JetBrains, vim, etc.).

Pour VS Code, les extensions recommandées : Python, Pylance, Ruff, Docker, YAML.

## Problèmes courants

Voir [`troubleshooting.md`](troubleshooting.md).
