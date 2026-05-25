# Testing strategy

## Scope

| Type             | Target                                                 | External deps        | Where it runs           |
|------------------|--------------------------------------------------------|----------------------|-------------------------|
| **Unit**         | Pure logic + FastAPI handlers with a mocked DB         | none                 | local dev, CI           |
| **Integration**  | FastAPI TestClient → real MariaDB → real DB            | MariaDB              | local dev (docker compose), CI (GHA service) |

> No E2E tests on OpenFaaS in CI (running OpenFaaS inside GHA = slow and brittle). The post-deployment smoke test relies on the Bruno collection.

## Tech stack

- [pytest](https://docs.pytest.org/) 8.x
- [`fastapi.testclient`](https://fastapi.tiangolo.com/tutorial/testing/) (httpx-based) for in-memory HTTP requests
- `unittest.mock` for DB mocks (unit tests)
- Markers: `unit`, `integration` (declared in `pyproject.toml`)

## Layout

```
tests/
├── conftest.py           # global fixtures: load_function, mock_pymysql, fernet_key, base_env
├── unit/
│   ├── test_generate_password.py
│   ├── test_generate_2fa.py
│   ├── test_authenticate_user.py
│   └── test_shared_modules.py     # db._read_secret, crypto, qr
└── integration/
    ├── conftest.py       # db_schema (session), truncate_users (each test), db_row helper
    └── test_full_flow.py
```

## Import isolation

Each of the 3 functions has its own `main.py` (and `db.py`, `crypto.py`, `qr.py`). To import the one under test without clashing in the `sys.modules` cache:

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

→ Each test loads **its** function via `load_function("generate-password")` and gets the matching `main` module.

## Running

### Everything

```bash
pytest                            # 36 tests: 30 unit + 6 integration (if MariaDB is up)
pytest --cov=functions --cov-report=term-missing
```

### Filter by marker

```bash
pytest -m unit                    # unit only, no Docker required
pytest -m integration             # integration only
pytest -m "not integration"       # skip MariaDB if it is down
```

### Filter by path / test

```bash
pytest tests/unit/test_authenticate_user.py
pytest -k "expired"               # every test whose name contains "expired"
pytest tests/unit/test_authenticate_user.py::test_invalid_otp -v
```

### Verbose mode + last failure

```bash
pytest --lf -vv                   # replay only the last failure
pytest --ff                       # start with previous failures
```

## Auto-skip of integration tests

`tests/integration/conftest.py` detects whether MariaDB is reachable:

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

→ Running `pytest` without `docker compose up` breaks nothing: only the unit tests are collected.

## DB fixtures

| Fixture          | Scope    | Role                                                            |
|------------------|----------|-----------------------------------------------------------------|
| `db_schema`      | session  | Creates the `users` table (from `deploy/init.sql`), DROP at the end |
| `truncate_users` | function | `TRUNCATE` before each test → isolation                         |
| `db_row(user)`   | function | Helper to read a row directly                                   |

## DB mocking (unit)

`mock_pymysql` patches `pymysql.connect` to return a `MagicMock` that supports the context manager. Tests then assert on `cursor.execute.call_args` to check the SQL query and its parameters:

```python
def test_handler_encrypts_password_before_storage(load_function, mock_pymysql):
    main = load_function("generate-password")
    _, cursor = mock_pymysql

    TestClient(main.app).post("/", json={"username": "alice"})

    _, params = cursor.execute.call_args[0]
    assert params[1].startswith("gAAAAA")  # Fernet token
```

## CI

Workflow [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml):

1. `ruff check .` + `ruff format --check .`
2. `pytest --cov=functions --cov-report=xml --junitxml=pytest-report.xml`
3. Build of the 3 Docker images (without push)

The `test` job spins up `mariadb:12` as a `services:` container with a health check; the credentials match the defaults in `tests/conftest.py`.

The `coverage.xml` and `pytest-report.xml` artifacts are uploaded at the end of the run (handy to wire up Codecov or a visualiser later).

## Coverage target

No blocking threshold configured — pragmatic for a PoC. Current coverage can be inspected locally with:

```bash
pytest --cov=functions --cov-report=html
# Open htmlcov/index.html
```

As a reference: > 90% on the 3 `main.py`, 100% on `crypto.py` and `qr.py`.

## Why integration tests instead of mocking everything?

The COFRAP brief mandates a precise DB schema (`id`, `username`, `password`, `mfa`, `gendate`, `expired`). Mocking every SQL call does not verify that the queries are **syntactically MariaDB-compatible**, nor that `ON DUPLICATE KEY UPDATE` behaves as expected. Integration tests guarantee the function ↔ DB contract holds against a real engine.
