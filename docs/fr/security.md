# Sécurité

## Modèle de menace (résumé)

Le sujet COFRAP a explicitement été remanié à cause de **comptes compromis dûs à des mots de passe faibles et à l'absence de 2FA**. La conception cible donc :

1. Empêcher les mots de passe faibles → génération aléatoire 24 caractères imposée.
2. Forcer la 2FA → activation dans le même flux que la création de compte.
3. Limiter la fenêtre de compromission → expiration à 6 mois automatique.
4. Protéger les credentials au repos → chiffrement Fernet en BDD.
5. Réduire la surface d'attaque réseau → fonctions invoquées uniquement via le gateway OpenFaaS.

Hors périmètre PoC (assuré par une autre équipe selon le sujet) :
- Rate limiting / anti-spam sur la création de compte
- Brute-force protection
- Détection d'anomalie (geo-IP, device fingerprint, etc.)

## Génération des mots de passe

- Longueur **fixe** à 24 caractères (cf. cahier des charges).
- Alphabet : `string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.<>?/"` (≈ 89 symboles).
- Source d'entropie : [`secrets.choice`](https://docs.python.org/3/library/secrets.html) — CSPRNG (`os.urandom` sous-jacent), pas `random`.
- Garantie de complexité : rejet et retirage tant que les 4 classes (lower, upper, digit, special) ne sont pas toutes représentées.

Entropie effective : ≈ 24 × log₂(89) ≈ **155 bits** — très au-delà des 80 bits recommandés par NIST SP 800-63B pour un secret aléatoire.

## Chiffrement au repos

Les deux champs sensibles de la table `users` sont chiffrés avec **Fernet** (`cryptography.fernet`) :

- `password` : mot de passe en clair (avant transmission unique via QR) → token Fernet.
- `mfa` : secret TOTP base32 → token Fernet.

Fernet sous le capot :
- AES-128-CBC pour la confidentialité
- HMAC-SHA256 pour l'authenticité
- Timestamp embarqué — utile pour détecter les replays/déchiffrements suspects (non exploité ici).

La clé (32 bytes base64 url-safe) vit uniquement dans le secret OpenFaaS `encryption-key`, lu à l'exécution dans `/var/openfaas/secrets/encryption-key` (montée tmpfs par OpenFaaS).

> **Perte de la clé = perte de tous les comptes** chiffrés avec. La sauvegarder en dehors du cluster (vault d'entreprise).

## Transmission des secrets utilisateurs

- Le **mot de passe en clair** n'est jamais persisté ni loggé. Il sort de `generate-password` une seule fois, encodé dans un PNG QR retourné en base64. Le frontend doit l'afficher et inviter l'utilisateur à le scanner immédiatement, sans le réafficher.
- Le **secret TOTP** sort de `generate-2fa` sous deux formes redondantes (URI `otpauth://` + QR PNG). L'URI contient le secret en clair (base32) — c'est le standard ; la sécurité repose sur le canal TLS du gateway.
- **TLS impératif en production** côté gateway OpenFaaS (cert-manager + Let's Encrypt via `arkade install openfaas-ingress`).

## CORS

Les 3 fonctions activent le `CORSMiddleware` de FastAPI pour que le frontend (servi depuis une autre origine) puisse les appeler depuis le navigateur. Origines pilotées par `CORS_ALLOW_ORIGINS` (`*` par défaut, ou liste explicite séparée par virgules).

- L'API **n'utilise aucun cookie** : l'authentification passe par le corps JSON. `allow_credentials` est donc désactivé — ce qui évite le piège « `*` + credentials » interdit par la spec CORS.
- En **production**, restreindre `CORS_ALLOW_ORIGINS` à l'origine réelle du frontend (ex. `https://app.cofrap.example.com`) plutôt que `*`.
- Le CORS est une protection **navigateur**, pas un contrôle d'accès serveur : il ne remplace ni l'authentification ni le rate limiting. Un client non-navigateur (curl, script) ignore le CORS.

## Rotation à 6 mois

Implémentée au niveau de la fonction `authenticate-user`, pas via un job cron :

```python
SIX_MONTHS_SECONDS = 60 * 60 * 24 * 30 * 6  # ≈ 15 552 000 s

if now - gendate > SIX_MONTHS_SECONDS or expired:
    UPDATE users SET expired = 1 WHERE username = ...
    return { authenticated: false, expired: true, action: "regenerate_password_and_2fa" }
```

Avantages :
- Pas de dépendance à un scheduler externe.
- Le contrôle est *effectif au moment où il est consommé* : un compte expiré qui n'est jamais utilisé reste à `expired = 0`, ce qui est cohérent (rien à régénérer si l'utilisateur ne se connecte plus).

Variable d'environnement `EXPIRY_SECONDS` pour overrider la fenêtre en test (utile pour démontrer le scénario expiré sans attendre 6 mois).

## Stockage et accès aux secrets

| Secret              | Stockage cible                              | Lu par                          |
|---------------------|---------------------------------------------|---------------------------------|
| `encryption-key`    | Secret OpenFaaS (montage `/var/openfaas/secrets/`) | `crypto.py` au démarrage d'une requête |
| `mariadb-password`  | Secret OpenFaaS                             | `db.py` à chaque ouverture de connexion |
| MariaDB credentials | `Secret` Kubernetes `mariadb-credentials`   | Le pod MariaDB (`envFrom`)      |

Aucun secret n'est commité — voir [`deploy/mariadb/secret.yaml`](../../deploy/mariadb/secret.yaml) qui contient des **placeholders à éditer** avant `kubectl apply`.

Le pattern `_read_secret(name)` (cf. `functions/*/crypto.py`) :
1. Lit `/var/openfaas/secrets/<name>` si présent (cas OpenFaaS prod).
2. Sinon fallback sur la variable d'env `<NAME_IN_SNAKE_UPPER>` (cas dev local ou CI).

## Conteneurs

- Image Python `slim` minimaliste.
- Utilisateur non-root (UID `10001`) — créé dans le `Dockerfile`, déclaré numériquement pour que Kubelet puisse vérifier `runAsNonRoot`.
- `HEALTHCHECK` Docker sur `/healthz` (non utilisé par Kubernetes mais utile en `docker run` direct).
- of-watchdog en mode HTTP — pas de fork-exec par requête, plus performant et plus simple à auditer.

## Bibliothèques

Versions épinglées dans chaque `requirements.txt`. À auditer périodiquement avec :

```bash
pip-audit -r functions/generate-password/requirements.txt
```

`pip-audit` n'est pas dans la CI actuellement — point d'amélioration documenté dans [`adr/`](adr/).

## Recommandations pour passer en production

Au-delà du périmètre PoC :

1. Ajouter du rate limiting au niveau du gateway OpenFaaS ou en amont (Cloudflare, ingress NGINX `limit_req`).
2. Activer mTLS entre les fonctions et MariaDB.
3. Mettre la clé Fernet dans un KMS managé (AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault) plutôt qu'en secret K8s.
4. Audit log applicatif (qui s'est authentifié, succès/échec, IP) avec rétention adaptée.
5. Tests adversariaux (OWASP ZAP, Burp) sur le gateway exposé.
6. SBOM et signing des images (déjà activés dans le workflow `release.yml` via `provenance: true` et `sbom: true`).
