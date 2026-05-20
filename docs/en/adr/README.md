# Architecture Decision Records

Lightweight format (title + context + decision + consequences). One ADR per structural choice.

| ADR                                                   | Decision                                                   |
|-------------------------------------------------------|------------------------------------------------------------|
| [0001](0001-openfaas-over-knative-or-functions.md)    | OpenFaaS Community over Knative or Cloud Functions         |
| [0002](0002-fastapi-with-of-watchdog.md)              | FastAPI/Uvicorn as the upstream of of-watchdog HTTP        |
| [0003](0003-fernet-for-at-rest-encryption.md)         | Fernet (cryptography) for password and MFA in the DB       |
| [0004](0004-mariadb-statefulset-no-orm.md)            | MariaDB StatefulSet + raw PyMySQL, no ORM                  |
| [0005](0005-expiry-check-at-auth-not-cron.md)         | Expiry check at login, not via a cron job                  |
| [0006](0006-duplicate-shared-utilities.md)            | Controlled duplication of shared modules across functions  |
