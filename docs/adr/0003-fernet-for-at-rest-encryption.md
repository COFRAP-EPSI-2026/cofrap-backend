# ADR 0003 — Fernet pour le chiffrement at-rest

**Statut** : Accepté
**Date** : 2026-05-19

## Contexte

Le sujet impose le chiffrement de `password` et `mfa` en BDD. Alternatives évaluées :

- **bcrypt/argon2 (hash)** — incompatible : on a besoin de **déchiffrer** le mot de passe au login (le cahier des charges décrit une vérification par comparaison après déchiffrement, pas un hash).
- **AES-GCM nu** (`cryptography.hazmat`) — plus de contrôle mais nécessite de gérer nonce, tag, format.
- **Fernet** (`cryptography.fernet`) — wrapper haut niveau standardisé.
- **libsodium / secretbox** — équivalent fonctionnellement, mais dépendance C supplémentaire.

## Décision

**Fernet** :
- AES-128-CBC + HMAC-SHA256 authentifié.
- Token base64 url-safe (compatible TEXT MariaDB sans encodage).
- Inclut timestamp interne (utile pour détection de replay future).
- API minimale : `Fernet(key).encrypt(plaintext)` / `.decrypt(token)`.

## Conséquences

✅ Implémentation triviale, peu de surface d'erreur.
✅ Format MultiFernet (déjà inclus dans `cryptography`) permet une rotation de clé sans downtime.
✅ Tokens identifiables (commencent par `gAAAAA…`), facile à valider en test.

⚠️ Clé symétrique unique — perte = perte des comptes. Mitigation : à industrialiser via KMS si passage en prod (cf. [`security.md`](../security.md#recommandations-pour-passer-en-production)).
⚠️ Pas de rotation automatique implémentée dans le PoC — opération manuelle si nécessaire.
