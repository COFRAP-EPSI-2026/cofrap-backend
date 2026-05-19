#!/usr/bin/env bash
# Create the OpenFaaS secrets consumed by the COFRAP functions.
# Run after `faas-cli login`, before `faas-cli up`.
#
# Generate a Fernet key with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

set -euo pipefail

: "${MARIADB_PASSWORD:?MARIADB_PASSWORD must be set}"
: "${ENCRYPTION_KEY:?ENCRYPTION_KEY must be set (Fernet key, 32 url-safe base64 bytes)}"

faas-cli secret create mariadb-password --from-literal "$MARIADB_PASSWORD"
faas-cli secret create encryption-key   --from-literal "$ENCRYPTION_KEY"
