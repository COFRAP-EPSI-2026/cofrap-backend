# Collection Bruno — COFRAP Backend

Collection de requêtes prêtes à l'emploi pour les 3 fonctions OpenFaaS du PoC.

## Ouverture

Installer [Bruno](https://www.usebruno.com/), puis `Open Collection` → sélectionner ce dossier `bruno/`.

## Environnements

Sélectionner via le sélecteur d'environnement (haut-droite de Bruno) avant de lancer une requête.

| Env                          | Quand l'utiliser                                                                                   |
|-------------------------------|----------------------------------------------------------------------------------------------------|
| **Local Direct**              | Dev rapide d'une fonction isolée — `uvicorn main:app --port <N>` sur 5001/5002/5003                |
| **Local OpenFaaS Gateway**    | Cluster local (K3S/minikube) avec OpenFaaS installé, gateway port-forwardé sur 127.0.0.1:8080      |
| **Cluster**                   | Cluster déployé (cloud, homelab) — éditer l'URL                                                    |

Le pattern d'URL est encapsulé dans 3 variables d'env par fonction :

| Variable                  | Local Direct                      | Local OpenFaaS Gateway                                  |
|---------------------------|-----------------------------------|----------------------------------------------------------|
| `generate_password_url`   | `http://127.0.0.1:5001`           | `http://127.0.0.1:8080/function/generate-password`       |
| `generate_2fa_url`        | `http://127.0.0.1:5002`           | `http://127.0.0.1:8080/function/generate-2fa`            |
| `authenticate_user_url`   | `http://127.0.0.1:5003`           | `http://127.0.0.1:8080/function/authenticate-user`       |

→ Toutes les requêtes utilisent `{{<fn>_url}}`. Pas besoin de toucher aux .bru pour switcher de mode, juste changer d'environnement.

## Lancer les fonctions en local (env "Local Direct")

```bash
docker compose up -d

# 3 terminaux séparés (avec PowerShell/bash, mêmes vars d'env exportées depuis .env)
cd functions/generate-password    && uvicorn main:app --port 5001
cd functions/generate-2fa         && uvicorn main:app --port 5002
cd functions/authenticate-user    && uvicorn main:app --port 5003
```

## Variables d'environnement (collection)

| Variable      | Rempli par                                                       | Rôle                                          |
|---------------|------------------------------------------------------------------|-----------------------------------------------|
| `username`    | manuel (défaut `michel.ranu`)                                    | Login de test                                 |
| `gendate`     | auto, post-réponse de `Generate password` / `Generate 2FA`       | Timestamp Unix de la dernière génération      |
| `totp_secret` | auto, post-réponse de `Generate 2FA` (extrait de l'URI)          | Permet le calcul du TOTP côté Bruno           |
| `password`    | **manuel** — à coller après scan du QR                           | Mot de passe en clair (24 caractères)         |
| `otp`         | auto, pre-request script de la requête d'auth                    | Code à 6 chiffres recalculé à chaque envoi    |

## Flux nominal

1. **`00 Health/*`** — sanity check, vérifie que les 3 fonctions répondent.
2. **`01 Onboarding/1. Generate password`** — crée l'utilisateur. Le QR PNG retourné en base64 doit être affiché et scanné pour récupérer le mot de passe en clair.
   - Astuce rapide : copier `qrcode_png_base64` depuis la réponse, ouvrir un onglet `data:image/png;base64,<la-valeur>` dans le navigateur, scanner avec un téléphone.
   - Coller le mot de passe obtenu dans la variable `password` de l'environnement.
3. **`01 Onboarding/2. Generate 2FA`** — génère le secret TOTP. Le script post-réponse extrait `secret=` de l'URI `otpauth://` et le stocke dans `totp_secret` (pratique pour les tests). Optionnellement, scanner le QR avec Google Authenticator.
4. **`02 Authentication/Authenticate (auto TOTP)`** — devrait renvoyer `authenticated: true`. Si non, vérifier que `password` est bien renseigné et que `totp_secret` est dans l'env.

## Cas d'erreur couverts

`02 Authentication/` : mauvais mot de passe, mauvais OTP, utilisateur inconnu, compte expiré.

`03 Validation/` : erreurs Pydantic (username vide ou absent, OTP trop court ou non numérique) et 404 sur `generate-2fa` avant `generate-password`.

## Pourquoi un calcul TOTP côté Bruno ?

`Authenticate (auto TOTP)` contient un **pre-request script** qui implémente HOTP/TOTP (RFC 6238) en JS pur via le module `crypto` de Node — pas de dépendance externe. Il décode le secret base32 stocké dans `totp_secret` et calcule le code à 6 chiffres pour la fenêtre de 30 s en cours. Cela permet de tester le chemin "succès" sans dépendre d'un téléphone, tout en gardant le scénario crédible (le serveur valide bien le code TOTP).

## Import depuis l'OpenAPI

L'API spec OpenAPI 3.1 est dans [`docs/openapi.yaml`](../docs/openapi.yaml). Bruno supporte l'import OpenAPI (`Collection → Import → OpenAPI`) si vous voulez regénérer la collection à partir du contrat plutôt que de l'éditer à la main.
