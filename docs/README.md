# Documentation

Documentation détaillée du PoC COFRAP backend. Le `README.md` à la racine est la porte d'entrée — ce dossier contient les approfondissements.

| Document                              | Pour qui ?                  | Quoi                                                              |
|---------------------------------------|-----------------------------|-------------------------------------------------------------------|
| [`architecture.md`](architecture.md)  | Reviewer technique, jury    | Choix techniques, diagrammes, flux end-to-end                     |
| [`api.md`](api.md)                    | Frontend, intégrateurs      | Référence des 3 fonctions : payloads, codes erreur, exemples curl |
| [`openapi.yaml`](openapi.yaml)        | Intégrateurs, outils        | Contrat machine-lisible (OpenAPI 3.1) — généré depuis FastAPI     |
| [`deployment.md`](deployment.md)      | Ops, équipe infra COFRAP    | Cluster K8s, OpenFaaS, MariaDB, secrets, options cloud/baremetal  |
| [`security.md`](security.md)          | Reviewer sécurité           | Modèle de menace, chiffrement, rotation, secrets                  |
| [`development.md`](development.md)    | Contributeurs               | Setup local, conventions, tests, debugging                        |
| [`testing.md`](testing.md)            | Contributeurs               | Stratégie unit/integration, exécution locale et CI                |
| [`troubleshooting.md`](troubleshooting.md) | Tout le monde         | Erreurs fréquentes et leur résolution                             |
| [`adr/`](adr/)                        | Reviewer technique          | Architecture Decision Records — choix structurants justifiés      |
