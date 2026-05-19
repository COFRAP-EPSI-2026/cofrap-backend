# Architecture Decision Records

Format léger (titre + contexte + décision + conséquences). Une ADR par choix structurant.

| ADR                                                   | Décision                                                   |
|-------------------------------------------------------|------------------------------------------------------------|
| [0001](0001-openfaas-over-knative-or-functions.md)    | OpenFaaS Community plutôt que Knative ou Cloud Functions   |
| [0002](0002-fastapi-with-of-watchdog.md)              | FastAPI/Uvicorn upstream de of-watchdog HTTP               |
| [0003](0003-fernet-for-at-rest-encryption.md)         | Fernet (cryptography) pour password et MFA en BDD          |
| [0004](0004-mariadb-statefulset-no-orm.md)            | MariaDB StatefulSet + PyMySQL brut, pas d'ORM              |
| [0005](0005-expiry-check-at-auth-not-cron.md)         | Contrôle d'expiration au login, pas via job cron           |
| [0006](0006-duplicate-shared-utilities.md)            | Duplication contrôlée des modules partagés entre fonctions |
