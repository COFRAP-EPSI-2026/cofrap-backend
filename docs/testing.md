# Stratégie de tests

## Périmètre

| Type            | Cible                                                  | Dépendances externes | Lieu d'exécution        |
|-----------------|--------------------------------------------------------|----------------------|-------------------------|
| **Unitaires**   | Logique pure + handlers FastAPI avec BDD mockée        | aucune               | dev local, CI           |
| **Intégration** | TestClient FastAPI → vraie MariaDB → vraie BDD        | MariaDB              | dev local (docker compose), CI (service GHA) |

> Pas de tests E2E sur OpenFaaS dans la CI (lance OpenFaaS dans GHA = lent et fragile). Le smoke test post-déploiement repose sur la collection Bruno.

## Stack technique

- [pytest](https://docs.pytest.org/) 8.x
- [`fastapi.testclient`](https://fastapi.tiangolo.com/tutorial/testing/) (basé sur httpx) pour les requêtes HTTP en mémoire
- `unittest.mock` pour les mocks BDD (unitaires)
- Markers : `unit`, `integration` (déclarés dans `pyproject.toml`)

## Organisation

```
tests/
├── conftest.py           # fixtures globales : load_function, mock_pymysql, fernet_key, base_env
├── unit/
│   ├── test_generate_password.py
│   ├── test_generate_2fa.py
│   ├── test_authenticate_user.py
│   └── test_shared_modules.py     # db._read_secret, crypto, qr
└── integration/
    ├── conftest.py       # db_schema (session), truncate_users (chaque test), db_row helper
    └── test_full_flow.py
```

## Isolation des imports

Les 3 fonctions ont chacune un fichier `main.py` (et `db.py`, `crypto.py`, `qr.py`). Pour pouvoir importer celle qu'on teste sans conflit dans le cache `sys.modules` :

```python
@pytest.fixture
def load_function(monkeypatch):
    def _load(function_name: str):
        monkeypatch.syspath_prepend(str(FUNCTIONS / function_name))
        for mod in ("main", "db", "crypto", "qr"):
            monkeypatch.delitem(sys.modules, mod, raising=False)
        return importlib.import_module("main")
    return _load
```

→ Chaque test charge **sa** fonction via `load_function("generate-password")` et obtient le module `main` correspondant.

## Exécution

### Tout

```bash
pytest                            # 36 tests : 30 unitaires + 6 intégration (si MariaDB up)
pytest --cov=functions --cov-report=term-missing
```

### Filtrer par marker

```bash
pytest -m unit                    # unitaires seulement, pas de Docker requis
pytest -m integration             # intégration seulement
pytest -m "not integration"       # éviter MariaDB si elle est down
```

### Filtrer par chemin / test

```bash
pytest tests/unit/test_authenticate_user.py
pytest -k "expired"               # tous les tests dont le nom contient "expired"
pytest tests/unit/test_authenticate_user.py::test_invalid_otp -v
```

### Mode verbeux + dernier échec

```bash
pytest --lf -vv                   # rejoue uniquement le dernier échec
pytest --ff                       # commence par les échecs précédents
```

## Skip auto des tests d'intégration

`tests/integration/conftest.py` détecte si MariaDB est joignable :

```python
def _is_mariadb_reachable() -> bool:
    try:
        pymysql.connect(connect_timeout=2, **_conn_kwargs()).close()
    except Exception:
        return False
    return True

if not _is_mariadb_reachable():
    collect_ignore_glob = ["test_*.py"]
```

→ Lancer `pytest` sans `docker compose up` ne casse rien : seuls les unitaires sont collectés.

## Fixtures BDD

| Fixture          | Scope    | Rôle                                                            |
|------------------|----------|-----------------------------------------------------------------|
| `db_schema`      | session  | Crée la table `users` (depuis `deploy/init.sql`), DROP à la fin |
| `truncate_users` | function | `TRUNCATE` avant chaque test → isolation                        |
| `db_row(user)`   | function | Helper de lecture directe d'une ligne                           |

## Mocking BDD (unit)

`mock_pymysql` patche `pymysql.connect` pour retourner un `MagicMock` qui supporte le context manager. Les tests asserent ensuite sur `cursor.execute.call_args` pour vérifier la requête SQL et les paramètres :

```python
def test_handler_encrypts_password_before_storage(load_function, mock_pymysql):
    main = load_function("generate-password")
    _, cursor = mock_pymysql

    TestClient(main.app).post("/", json={"username": "alice"})

    _, params = cursor.execute.call_args[0]
    assert params[1].startswith("gAAAAA")  # token Fernet
```

## CI

Workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) :

1. `ruff check .` + `ruff format --check .`
2. `pytest --cov=functions --cov-report=xml --junitxml=pytest-report.xml`
3. Build des 3 images Docker (sans push)

Le job `test` monte `mariadb:11` en `services:` avec health-check ; les credentials matchent les défauts du `tests/conftest.py`.

Les artefacts `coverage.xml` et `pytest-report.xml` sont uploadés en fin de run (utiles pour brancher Codecov ou un visualizer plus tard).

## Couverture cible

Pas de seuil bloquant configuré — pragmatique pour un PoC. La couverture actuelle est consultable en local avec :

```bash
pytest --cov=functions --cov-report=html
# Ouvrir htmlcov/index.html
```

À titre indicatif : > 90% sur les 3 `main.py`, 100% sur `crypto.py` et `qr.py`.

## Pourquoi des tests d'intégration au lieu de tout mocker ?

Le sujet COFRAP impose un schéma BDD précis (`id`, `username`, `password`, `mfa`, `gendate`, `expired`). Mocker tous les appels SQL ne valide pas que les requêtes sont **syntaxiquement compatibles MariaDB** ni que `ON DUPLICATE KEY UPDATE` se comporte comme attendu. Les tests d'intégration garantissent que le contrat fonction ↔ BDD tient face à un vrai moteur.
