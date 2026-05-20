# Documentation

Detailed documentation for the COFRAP backend PoC. The root `README.md` is the entry point — this folder holds the deep dives.

> 🇫🇷 Version française : [`docs/fr/`](../fr/README.md)

| Document                              | Audience                    | Content                                                           |
|---------------------------------------|-----------------------------|-------------------------------------------------------------------|
| [`installation.md`](installation.md)  | Ops, devs                   | Step-by-step install on K3s / minikube / existing cluster (Windows + Linux) |
| [`architecture.md`](architecture.md)  | Technical reviewer, jury    | Technical choices, diagrams, end-to-end flow                      |
| [`api.md`](api.md)                    | Frontend, integrators       | Reference of the 3 functions: payloads, error codes, curl examples |
| [`openapi.yaml`](../openapi.yaml)     | Integrators, tooling        | Machine-readable contract (OpenAPI 3.1) — generated from FastAPI  |
| [`deployment.md`](deployment.md)      | Ops, COFRAP infra team      | K8s cluster, OpenFaaS, MariaDB, secrets, cloud/baremetal options  |
| [`security.md`](security.md)          | Security reviewer           | Threat model, encryption, rotation, secrets                       |
| [`development.md`](development.md)    | Contributors                | Local setup, conventions, tests, debugging                        |
| [`testing.md`](testing.md)            | Contributors                | Unit/integration strategy, local and CI execution                 |
| [`troubleshooting.md`](troubleshooting.md) | Everyone               | Common errors and how to fix them                                 |
| [`adr/`](adr/)                        | Technical reviewer          | Architecture Decision Records — justified structural choices      |
