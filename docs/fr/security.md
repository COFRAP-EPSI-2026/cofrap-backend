# Sécurité

## Modèle de menace (résumé)

Le sujet COFRAP a explicitement été remanié à cause de **comptes compromis dûs à des mots de passe faibles et à l'absence de 2FA**. La conception cible donc :

1. Empêcher les mots de passe faibles → génération aléatoire 24 caractères imposée.
2. Forcer la 2FA → activation dans le même flux que la création de compte.
3. Limiter la fenêtre de compromission → expiration à 6 mois automatique.
4. Protéger les credentials au repos → chiffrement Fernet en BDD.
5. Réduire la surface d'attaque réseau → fonctions invoquées uniquement via le gateway OpenFaaS.

Implémenté en plus du sujet, pour rester sain en charge :
- **Rate limiting applicatif** (slowapi, par IP) sur les 3 fonctions
- **`max_inflight` of-watchdog** (limite de requêtes concurrentes par pod)
- **Timeouts DB** (connect / read / write) pour libérer rapidement les connexions bloquées

Hors périmètre PoC (assuré par une autre équipe selon le sujet) :
- Brute-force protection (verrouillage du compte après N échecs côté serveur — le frontend fait un lock-out local)
- Détection d'anomalie (geo-IP, device fingerprint, etc.)
- WAF / anti-spam en bordure (Cloudflare, NGINX `limit_req`)

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

## Rate limiting (slowapi)

Chaque fonction câble un `Limiter` [slowapi](https://github.com/laurentS/slowapi) + `SlowAPIMiddleware`. Au-delà du quota par IP, l'API renvoie `429 Too Many Requests` avec `{"detail":"rate limit exceeded"}`.

Configuration via variables d'environnement (héritables sans rebuild de l'image) :

| Variable               | Défaut       | Effet                                                                          |
|------------------------|--------------|--------------------------------------------------------------------------------|
| `RATE_LIMIT`           | `120/minute` | Quota par IP. Syntaxe slowapi : `"<n>/<period>"` (`second`, `minute`, `hour`, `day`). |
| `RATE_LIMIT_ENABLED`   | `true`       | Mettre à `false` désactive complètement le middleware (utile en test).         |

Clé de comptage : l'IP est lue en priorité dans l'en-tête `X-Forwarded-For` (premier hop), sinon via `slowapi.util.get_remote_address`. Côté cluster, c'est donc l'IP **client réelle** qui est limitée même derrière le gateway OpenFaaS et un Ingress NGINX/Traefik — à condition que le reverse-proxy en amont remplisse `X-Forwarded-For` (cas standard).

Le healthcheck `/healthz` est annoté `@limiter.exempt` — il reste joignable par les probes Kubernetes même sous attaque.

> **Limites de l'implémentation** : slowapi maintient le compteur **en mémoire dans chaque pod**. Avec plusieurs replicas, le quota effectif est *(replicas) × RATE_LIMIT*. Pour un quota global strict, brancher slowapi sur un backend partagé (Redis) ou déplacer le rate-limit sur l'Ingress/le gateway.

## of-watchdog `max_inflight`

Chaque `Dockerfile` fixe `ENV max_inflight="10"` : c'est la **borne dure** sur le nombre de requêtes traitées simultanément par un pod. Au-delà, of-watchdog lui-même renvoie `429` — la fonction Python n'est pas appelée, ce qui évite que la queue uvicorn n'explose et que les connexions MariaDB ne saturent.

Combiné au rate-limit slowapi, on a une protection en deux couches :

1. **slowapi** filtre les rafales d'une même IP (HTTP applicatif).
2. **max_inflight** plafonne la charge réelle quel que soit le nombre de clients.

## Timeouts MariaDB

`db.py` passe à `pymysql.connect()` les trois timeouts suivants (overridables par env, valeurs en secondes) :

| Variable             | Défaut | Effet                                                       |
|----------------------|--------|-------------------------------------------------------------|
| `DB_CONNECT_TIMEOUT` | `5`    | Délai max pour établir la connexion TCP/SSL                 |
| `DB_READ_TIMEOUT`    | `10`   | Délai max pour recevoir une réponse à une requête           |
| `DB_WRITE_TIMEOUT`   | `10`   | Délai max pour envoyer une requête                          |

Effet pratique : si MariaDB est lente, gelée ou perd la connexion, la fonction renvoie une erreur **en quelques secondes** au lieu d'attendre indéfiniment et de bloquer un slot `max_inflight`.

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

1. Brancher slowapi sur un **store partagé** (Redis) pour rendre le rate-limit global aux replicas, ou déplacer la limite sur l'Ingress / le gateway OpenFaaS.
2. Activer mTLS entre les fonctions et MariaDB.
3. Mettre la clé Fernet dans un **KMS managé** (AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault) plutôt qu'en secret K8s.
4. Audit log applicatif (qui s'est authentifié, succès/échec, IP) avec rétention adaptée.
5. Tests adversariaux (OWASP ZAP, Burp) sur le gateway exposé.
6. Réactiver les attestations supply-chain (`provenance: true` + `sbom: true`) une fois qu'un registre supportant les attestations OCI est en place — désactivées actuellement sur GHCR car elles introduisent des entrées `unknown/unknown` dans la liste des architectures (cf. [`deployment.md`](deployment.md)).
