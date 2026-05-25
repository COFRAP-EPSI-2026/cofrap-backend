"""Génère `docs/openapi.yaml` à partir des 3 apps FastAPI.

Usage :
    python scripts/generate-openapi.py

Comportement :
- Charge les 3 fonctions (generate-password, generate-2fa, authenticate-user) en isolant leurs imports.
- Récupère le schéma OpenAPI auto-généré par FastAPI (`app.openapi()`).
- Préfixe les paths (`/function/<name>`) et les schémas (`<name_snake>_<Schema>`) pour éviter les collisions.
- Ajoute serveurs, tags, métadonnées globales.
- Écrit le résultat en YAML dans `docs/openapi.yaml`.

Re-lancer ce script après toute modification d'un `main.py` ou d'un modèle Pydantic.
"""

from __future__ import annotations

import importlib
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS_DIR = ROOT / "functions"
OUTPUT_PATH = ROOT / "docs" / "openapi.yaml"

FUNCTIONS = ["generate-password", "generate-2fa", "authenticate-user"]
SHARED_MODULES = ("main", "db", "crypto", "qr")


def _load_app(function_name: str):
    """Importe le `main.py` d'une fonction en isolant le cache sys.modules."""
    function_dir = FUNCTIONS_DIR / function_name
    sys.path.insert(0, str(function_dir))
    try:
        for mod in SHARED_MODULES:
            sys.modules.pop(mod, None)
        module = importlib.import_module("main")
        return module.app
    finally:
        sys.path.remove(str(function_dir))


def _rewrite_refs(obj: Any, prefix: str) -> Any:
    """Préfixe les `$ref` qui pointent vers `#/components/schemas/<Name>`."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str) and v.startswith("#/components/schemas/"):
                schema_name = v.removeprefix("#/components/schemas/")
                result[k] = f"#/components/schemas/{prefix}_{schema_name}"
            else:
                result[k] = _rewrite_refs(v, prefix)
        return result
    if isinstance(obj, list):
        return [_rewrite_refs(x, prefix) for x in obj]
    return obj


def _function_prefix(function_name: str) -> str:
    return function_name.replace("-", "_")


def _base_spec() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "COFRAP Backend API",
            "version": "2026.2.0",  # x-release-please-version
            "summary": "PoC COFRAP — génération de mot de passe, 2FA TOTP et authentification.",
            "description": (
                "API serverless (OpenFaaS) du PoC COFRAP. "
                "Trois fonctions Python/FastAPI exposées via le gateway OpenFaaS, "
                "persistance en MariaDB, chiffrement at-rest des credentials (Fernet)."
            ),
            "contact": {
                "name": "COFRAP-EPSI-2026",
                "url": "https://github.com/COFRAP-EPSI-2026/cofrap-backend",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        },
        "servers": [
            {
                "url": "http://127.0.0.1:8080",
                "description": "Local OpenFaaS gateway (port-forwardé)",
            },
            {
                "url": "https://openfaas.cofrap.example.com",
                "description": "Cluster déployé (placeholder à éditer)",
            },
        ],
        "tags": [
            {
                "name": "generate-password",
                "description": "Génère un mot de passe 24 caractères, chiffré et stocké, transmis via QR.",
            },
            {
                "name": "generate-2fa",
                "description": "Génère un secret TOTP (RFC 6238) pour un utilisateur existant.",
            },
            {
                "name": "authenticate-user",
                "description": "Authentifie un utilisateur, contrôle l'ancienneté (6 mois).",
            },
        ],
        "paths": {},
        "components": {"schemas": {}},
    }


def merge_specs() -> dict:
    merged = _base_spec()

    for function_name in FUNCTIONS:
        prefix = _function_prefix(function_name)
        app = _load_app(function_name)
        spec = deepcopy(app.openapi())

        base_path = f"/function/{function_name}"

        for path, methods in spec.get("paths", {}).items():
            full_path = base_path if path == "/" else f"{base_path}{path}"
            for op in methods.values():
                if isinstance(op, dict):
                    existing_tags = op.get("tags", []) or []
                    op["tags"] = [function_name, *[t for t in existing_tags if t != function_name]]
                    # Préfixer operationId pour éviter les collisions (3 fonctions ont chacune `healthz`)
                    if "operationId" in op:
                        op["operationId"] = f"{prefix}_{op['operationId']}"
            merged["paths"][full_path] = _rewrite_refs(methods, prefix)

        schemas = spec.get("components", {}).get("schemas", {})
        for schema_name, schema in schemas.items():
            merged["components"]["schemas"][f"{prefix}_{schema_name}"] = _rewrite_refs(
                schema, prefix
            )

    return merged


def dump_yaml(spec: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Généré par scripts/generate-openapi.py — NE PAS ÉDITER À LA MAIN.\n"
        "# Re-lancer après modification d'un main.py ou d'un modèle Pydantic.\n\n"
    )
    yaml_body = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120)
    path.write_text(header + yaml_body, encoding="utf-8")


def main() -> None:
    spec = merge_specs()
    dump_yaml(spec, OUTPUT_PATH)
    rel = OUTPUT_PATH.relative_to(ROOT)
    print(
        f"OK - {len(spec['paths'])} endpoints, "
        f"{len(spec['components']['schemas'])} schemas -> {rel}"
    )


if __name__ == "__main__":
    main()
