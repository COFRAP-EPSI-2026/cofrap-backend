# Référence API

Chaque fonction est invoquée via le gateway OpenFaaS sur `POST /function/<name>`. Toutes les réponses sont en JSON, encodées UTF-8.

URL de base : `{{gateway}}/function/`

> **Contrat machine-lisible** : [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1) — généré automatiquement depuis les apps FastAPI par [`scripts/generate-openapi.py`](../scripts/generate-openapi.py). À ouvrir dans [Swagger Editor](https://editor.swagger.io/), [Redocly](https://redocly.github.io/redoc/) ou n'importe quel client API (Bruno, Postman, Insomnia) supportant l'import OpenAPI.

---

## `generate-password`

Génère un mot de passe à 24 caractères (majuscules, minuscules, chiffres, caractères spéciaux), le chiffre avec Fernet et le stocke dans MariaDB. Renvoie le QR code PNG (base64) à scanner pour récupérer le mot de passe en clair — **transmission à usage unique**.

Si l'utilisateur existe déjà (`ON DUPLICATE KEY UPDATE`), son mot de passe est régénéré et `expired` repasse à 0.

### Requête

```
POST /function/generate-password
Content-Type: application/json

{
  "username": "michel.ranu"
}
```

### Réponse 200

```json
{
  "username": "michel.ranu",
  "gendate": 1721916574,
  "qrcode_png_base64": "iVBORw0KGgoAAAANSUhEUg..."
}
```

| Code | Cas                                                |
|------|----------------------------------------------------|
| 200  | OK                                                 |
| 422  | `username` vide ou absent (validation Pydantic)    |
| 500  | Erreur BDD — la transaction est rollback           |

### Exemple curl

```bash
curl -s -X POST $GATEWAY/function/generate-password \
     -H 'Content-Type: application/json' \
     -d '{"username":"michel.ranu"}' \
  | jq -r .qrcode_png_base64 \
  | base64 -d > qr.png
```

---

## `generate-2fa`

Génère un secret TOTP base32, le chiffre, l'associe à l'utilisateur **existant**, et renvoie l'URI `otpauth://` + le QR à scanner avec une app authenticator.

### Requête

```
POST /function/generate-2fa
Content-Type: application/json

{
  "username": "michel.ranu"
}
```

### Réponse 200

```json
{
  "username": "michel.ranu",
  "gendate": 1721916600,
  "otpauth_uri": "otpauth://totp/COFRAP:michel.ranu?secret=JBSWY3DPEHPK3PXP&issuer=COFRAP",
  "qrcode_png_base64": "iVBORw0KGgoAAAANSUhEUg..."
}
```

| Code | Cas                                                                                |
|------|------------------------------------------------------------------------------------|
| 200  | OK                                                                                 |
| 404  | Utilisateur inconnu (`generate-password` non appelé au préalable)                  |
| 422  | `username` vide ou absent                                                          |
| 500  | Erreur BDD — la transaction est rollback                                           |

L'`issuer` affiché dans l'authenticator est configurable via la variable d'env `TOTP_ISSUER` (défaut `COFRAP`).

---

## `authenticate-user`

Authentifie un utilisateur. Contrôle l'ancienneté du compte avant la validation du mot de passe et du code TOTP.

### Requête

```
POST /function/authenticate-user
Content-Type: application/json

{
  "username": "michel.ranu",
  "password": "p<...24 chars...>",
  "otp": "123456"
}
```

`otp` doit matcher `^\d{6}$` — le contrôle se fait avant tout accès BDD.

### Réponse 200 — succès

```json
{
  "authenticated": true,
  "expired": false,
  "username": "michel.ranu"
}
```

### Réponse 200 — compte expiré

Renvoie un 200 (pas une erreur) avec une instruction explicite pour le frontend :

```json
{
  "authenticated": false,
  "expired": true,
  "action": "regenerate_password_and_2fa"
}
```

Le flag `expired` est passé à 1 en BDD au passage. Le frontend doit alors enchaîner `generate-password` puis `generate-2fa`.

### Autres codes

| Code | Cas                                                              |
|------|------------------------------------------------------------------|
| 401  | Mot de passe ou OTP invalide (`detail` indique lequel)           |
| 404  | Utilisateur inconnu                                              |
| 409  | Compte incomplet (`password` ou `mfa` `NULL` en BDD)             |
| 422  | Validation Pydantic (OTP < 6 chiffres ou non numérique, etc.)    |
| 500  | Erreur interne                                                   |

---

## Endpoints transverses

Chaque fonction expose `GET /healthz` qui renvoie `{"status": "ok"}`. C'est le sondage utilisé par le healthcheck Docker du `Dockerfile`.

---

## Tester l'API

Une collection Bruno complète est fournie dans [`bruno/`](../bruno/) — flux nominal et cas d'erreur prêts à l'emploi, avec calcul TOTP côté client pour automatiser le test d'authentification.
