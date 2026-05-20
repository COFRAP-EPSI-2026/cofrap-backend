# ADR 0006 — Duplication des modules partagés entre fonctions

**Statut** : Accepté
**Date** : 2026-05-19

## Contexte

`db.py`, `crypto.py` et `qr.py` ont une logique identique entre les 3 fonctions OpenFaaS. Options pour éviter la duplication :

1. **Package Python privé** publié sur un registry (PyPI privé, GitHub Packages) — workflow lourd pour 80 lignes de code.
2. **Build context partagé** où chaque fonction COPY `../shared/` — nécessite de builder depuis la racine, casse le workflow `faas-cli` natif.
3. **Liens symboliques** pendant le build — non portable Windows, fragile.
4. **Duplication contrôlée** : chaque fonction embarque ses copies.

## Décision

**Option 4** : chaque dossier `functions/<name>/` est self-contained. Les 3 copies de `db.py`/`crypto.py`/`qr.py` doivent être maintenues en miroir.

## Conséquences

✅ `faas-cli build -f <fn>.yml` fonctionne sans config custom.
✅ Le `Dockerfile` est trivial et autonome.
✅ Lecture facile : tout ce dont une fonction a besoin est dans son dossier.

⚠️ **Risque de drift** entre les copies. Mitigations :
- Tests unitaires partagés (`tests/unit/test_shared_modules.py`) qui valident le contrat depuis la copie de `generate-password` — si elle drift, le test casse.
- Si le drift devient un problème en pratique, passer à l'option 2 avec un build context à la racine (modifier `stack.yml` et tous les `Dockerfile`).

## Notes

Cette décision est explicitement temporaire — adaptée à un PoC à 3 fonctions. Au-delà de 5-6 fonctions, repenser pour publier un package partagé.
