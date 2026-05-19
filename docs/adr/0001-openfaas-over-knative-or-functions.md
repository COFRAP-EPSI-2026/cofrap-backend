# ADR 0001 — OpenFaaS Community comme runtime serverless

**Statut** : Accepté
**Date** : 2026-05-19

## Contexte

Le sujet MSPR impose explicitement OpenFaaS pour la fonctionnalité "Scale to Zero" demandée. Trois alternatives sérieuses existaient :

- **Knative Serving** sur Kubernetes — plus standard CNCF, plus complexe à mettre en œuvre.
- **Cloud Functions managés** (GCF, Azure Functions, AWS Lambda) — réduit drastiquement la complexité d'infrastructure mais sort du périmètre "Kubernetes" demandé.
- **OpenFaaS Community** — ciblé par le cahier des charges.

## Décision

Utiliser **OpenFaaS Community** avec :
- Le template `dockerfile` (pas `python3-http`) pour avoir un contrôle total sur l'image et permettre FastAPI/Uvicorn comme upstream HTTP via `of-watchdog`.
- `faas-cli` comme outil unique de build/push/deploy.
- Helm pour installer OpenFaaS sur le cluster.

## Conséquences

✅ Conformité au sujet.
✅ Communauté active, documentation riche, intégration native Kubernetes.
✅ Scale-to-zero disponible dans la version Community en mode "idle" (durée configurable).

⚠️ Pas de gestion fine multi-tenant (vs Knative). Acceptable pour un PoC mono-équipe.
⚠️ Couplage à `faas-cli` pour le déploiement — si on voulait migrer vers Knative, il faudrait réécrire le workflow de release.
