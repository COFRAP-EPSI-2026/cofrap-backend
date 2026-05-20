# ADR 0002 — FastAPI/Uvicorn upstream de of-watchdog HTTP

**Statut** : Accepté
**Date** : 2026-05-19

## Contexte

OpenFaaS propose plusieurs façons d'exécuter du Python :

1. Template officiel `python3-http` (Flask sous le capot).
2. Template `python3-debian` (Flask + libs natives).
3. **Image custom** avec `of-watchdog` en mode HTTP, qui forward vers un upstream local.

Le sujet COFRAP recommande FastAPI ; FastAPI n'a pas de template OpenFaaS officiel.

## Décision

**Option 3** : `Dockerfile` custom avec `of-watchdog` mode HTTP qui forward sur `127.0.0.1:5000` où tourne Uvicorn / FastAPI.

```dockerfile
ENV fprocess="uvicorn main:app --host 127.0.0.1 --port 5000"
ENV upstream_url="http://127.0.0.1:5000"
ENV mode="http"
CMD ["fwatchdog"]
```

## Conséquences

✅ FastAPI conserve toutes ses fonctionnalités : validation Pydantic, OpenAPI gratuit, async/await possible.
✅ of-watchdog en mode HTTP garde le process Uvicorn chaud entre les requêtes (pas de fork-exec par requête).
✅ Healthcheck Docker `wget /healthz` natif.

⚠️ Image légèrement plus grosse que les templates officiels (~150 Mo vs ~80 Mo).
⚠️ Le warm-up Uvicorn (~500 ms) ajoute du cold start. Acceptable pour le PoC ; à mesurer si le produit passe en prod.
