# ADR 0004 — MariaDB en StatefulSet et SQL brut (pas d'ORM)

**Statut** : Accepté
**Date** : 2026-05-19

## Contexte

Choix de l'hébergement BDD :

- VM dédiée hors cluster — autonomie, mais ressource externe à gérer.
- BDD managée cloud (Cloud SQL, RDS) — pas accessible dans le contexte PoC scolaire.
- **StatefulSet Kubernetes** — homogène avec le reste du déploiement.

Choix de l'accès Python :

- ORM SQLAlchemy / Tortoise — modélisation déclarative, migrations.
- Driver brut (PyMySQL, `mariadb`) — code direct, dépendances réduites.

## Décision

- MariaDB en **StatefulSet** avec un PVC de 2 Gi, image officielle `mariadb:11`.
- **PyMySQL** (pure Python) avec requêtes SQL paramétrées (`%s` placeholders).
- Pas d'ORM.

## Conséquences

✅ Image fonction minimaliste (PyMySQL = pure Python, pas de wheel natif).
✅ Une seule table figée par le sujet → un ORM est sur-dimensionné.
✅ Requêtes SQL visibles et auditables dans `main.py` de chaque fonction.

⚠️ Pas de migrations versionnées (acceptable pour un schéma figé).
⚠️ Si le schéma évoluait fortement, l'ajout d'Alembic deviendrait pertinent — décision à reconsidérer.
