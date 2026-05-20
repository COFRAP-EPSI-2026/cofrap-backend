"""Tests CORS — vérifie que les 3 fonctions exposent les en-têtes CORS au frontend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

FUNCTIONS = ["generate-password", "generate-2fa", "authenticate-user"]
ORIGIN = "http://localhost:5173"


@pytest.mark.parametrize("function_name", FUNCTIONS)
def test_preflight_allows_origin_by_default(load_function, function_name):
    """Une requête OPTIONS de préflight reçoit `access-control-allow-origin` (défaut `*`)."""
    main = load_function(function_name)
    client = TestClient(main.app)

    response = client.options(
        "/",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "*"


@pytest.mark.parametrize("function_name", FUNCTIONS)
def test_simple_request_has_cors_header(load_function, function_name):
    """Une requête réelle avec `Origin` reçoit l'en-tête CORS dans la réponse."""
    main = load_function(function_name)
    client = TestClient(main.app)

    response = client.get("/healthz", headers={"Origin": ORIGIN})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


@pytest.mark.parametrize("function_name", FUNCTIONS)
def test_explicit_origin_list(load_function, function_name, monkeypatch):
    """`CORS_ALLOW_ORIGINS` à liste explicite restreint l'origine renvoyée."""
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", f"{ORIGIN},https://app.cofrap.example.com")
    main = load_function(function_name)
    client = TestClient(main.app)

    allowed = client.get("/healthz", headers={"Origin": ORIGIN})
    assert allowed.headers.get("access-control-allow-origin") == ORIGIN

    # Une origine hors liste ne reçoit pas l'en-tête.
    rejected = client.get("/healthz", headers={"Origin": "https://evil.example.com"})
    assert rejected.headers.get("access-control-allow-origin") is None
