# Architecture

## Vue d'ensemble

Le PoC implémente le cycle de vie d'un compte utilisateur COFRAP :

1. Création du compte → mot de passe à 24 caractères, transmis **une seule fois** via QR code.
2. Activation de la 2FA → secret TOTP, transmis également via QR code.
3. Authentification → mot de passe + code TOTP, avec **expiration automatique à 6 mois**.

Le tout s'exécute en **serverless** (OpenFaaS Community) sur Kubernetes, avec MariaDB pour la persistance.

```
┌─────────────┐    HTTP/JSON    ┌──────────────────┐    SQL (TLS optionnel)    ┌────────────┐
│ Frontend    │ ───────────────►│ OpenFaaS Gateway │ ─────────────────────────►│  MariaDB   │
│ (TypeScript)│                 │   (Kubernetes)   │                            │ StatefulSet│
└─────────────┘                 │                  │                            └────────────┘
                                │  ├─ generate-password
                                │  ├─ generate-2fa
                                │  └─ authenticate-user
                                └──────────────────┘
                                        ▲
                                        │  secrets OpenFaaS (/var/openfaas/secrets/)
                                        │   ├─ mariadb-password
                                        │   └─ encryption-key (Fernet)
```

## Choix techniques

| Choix                    | Décision                              | Justification                                                                              |
|--------------------------|---------------------------------------|--------------------------------------------------------------------------------------------|
| Langage backend          | **Python 3.12**                       | Recommandé par le sujet COFRAP ; écosystème mature pour crypto/QR/TOTP                     |
| Framework HTTP           | **FastAPI** + Uvicorn (ASGI)          | Validation Pydantic gratuite, OpenAPI auto, performances ASGI                              |
| Runtime serverless       | **OpenFaaS Community** + of-watchdog  | Imposé par le sujet ; `Scale to Zero` aligné avec l'objectif d'économie d'échelle          |
| Conteneurs               | Image Python slim + of-watchdog HTTP  | Standard documenté ; permet à FastAPI/Uvicorn d'être upstream                              |
| Base de données          | **MariaDB 11** (StatefulSet K8s)      | SQL recommandé par le client ; simple, robuste, schéma plat à une seule table              |
| Driver Python            | **PyMySQL** (pure Python)             | Pas de dépendance native → image Python slim, build rapide en CI                           |
| Chiffrement applicatif   | **Fernet** (`cryptography`)           | AES-128-CBC + HMAC-SHA256 authentifié, API simple, rotation possible via clé multi-version |
| Génération TOTP          | **pyotp**                             | Implémentation RFC 6238 conforme Google Authenticator/Authy                                |
| Génération QR codes      | **qrcode** + PIL                      | PNG base64 retourné dans la réponse JSON — le frontend gère l'affichage                    |
| Frontend                 | **TypeScript** (dépôt séparé)         | Choix demandé ; PoC : juste assez d'UI pour démontrer le flux                              |

## Flux nominal d'un nouvel utilisateur

```
Frontend                generate-password           generate-2fa          authenticate-user           MariaDB
   │                          │                          │                          │                    │
   │── POST /username ───────►│                          │                          │                    │
   │                          │── INSERT user (enc pwd) ─────────────────────────────────────────────────►│
   │◄── QR PNG (24-char pwd) ─│                          │                          │                    │
   │                          │                          │                          │                    │
   │── POST /username ───────────────────────────────────►                          │                    │
   │                          │                          │── UPDATE mfa = enc(totp) ────────────────────►│
   │◄── QR PNG (otpauth:// ) ─────────────────────────────│                          │                    │
   │                          │                          │                          │                    │
   │── login + pwd + otp ─────────────────────────────────────────────────────────►│                    │
   │                          │                          │                          │── SELECT user ────►│
   │                          │                          │                          │◄── row ────────────│
   │◄── { authenticated: true } ──────────────────────────────────────────────────│                    │
```

## Flux d'un compte expiré

```
... 6 mois plus tard ...
   │── login + pwd + otp ────────────────────────────────►│
   │                                                       │── SELECT user
   │                                                       │   now - gendate > 6 mois → UPDATE expired = 1
   │◄── { authenticated: false, expired: true,             │
   │     action: "regenerate_password_and_2fa" } ─────────│
   │
   │── POST /username → generate-password ► relance le cycle
```

## Modèle de données

Une seule table — `users` — strictement conforme au schéma du cahier des charges :

```sql
CREATE TABLE users (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password TEXT NULL,        -- chiffré Fernet (jamais en clair)
    mfa      TEXT NULL,        -- secret TOTP chiffré Fernet
    gendate  BIGINT NOT NULL,  -- timestamp Unix de génération
    expired  TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_username (username),
    INDEX idx_expired_gendate (expired, gendate)
);
```

Pourquoi pas de colonnes supplémentaires ? Le sujet impose ce schéma minimaliste. Tout enrichissement (last_login, fail_count, audit log) sort du périmètre du PoC.

## Décisions structurantes

- **Pas de cron de rotation à 6 mois**. La fonction `authenticate-user` est le seul point de contrôle : à chaque login, elle compare `now - gendate` à la fenêtre de 6 mois. Avantage : aucune dépendance à un scheduler externe, l'état est cohérent au moment où il est consommé.
- **`generate-2fa` fait un UPDATE, pas un INSERT**. Un secret TOTP n'a de sens que pour un compte existant. Si le user n'existe pas → 404 explicite, le frontend doit d'abord appeler `generate-password`.
- **Le mot de passe en clair n'est exposé qu'une seule fois**, dans la réponse au scan QR. Aucun log applicatif ne doit le contenir.
- **Une copie des modules partagés (`db.py`, `crypto.py`, `qr.py`) dans chaque fonction**, plutôt qu'un package partagé. Raison : chaque fonction OpenFaaS construit son propre image avec son `Dockerfile` autonome. Le coût de duplication (≈ 40 lignes × 3) est inférieur au coût de gérer un build context partagé ou un package privé.

→ Détails supplémentaires dans [`adr/`](adr/).
