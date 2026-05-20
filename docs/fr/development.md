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

# Démarrer MariaDB locale
docker compose up -d
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

# Intégration seulement (nécessite docker compose up -d)
pytest -m integration

# Un seul test
pytest tests/unit/test_generate_password.py::test_password_meets_complexity -v
```

## Cycle de dev typique

1. Modifier `functions/<fn>/main.py` ou un module partagé.
2. `ruff check --fix . && ruff format .`
3. `pytest` (vert ?)
4. Tester en local : `uvicorn main:app --reload` puis curl ou la [collection Bruno](../../bruno/).
5. Commit + PR. La CI rejoue lint + tests + build des 3 images Docker.

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
