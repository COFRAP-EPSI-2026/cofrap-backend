# Troubleshooting

## Tests

### `pytest` me dit `OperationalError: Access denied for user 'cofrap'@'…'`

MariaDB tourne mais les credentials ne matchent pas. Vérifier que `docker-compose.yml` a bien démarré avec les défauts attendus :

```bash
docker compose down -v          # supprime aussi le volume → recréation propre
docker compose up -d
```

Le `volume mariadb_data` est persistant : si vous changez le `MARIADB_PASSWORD` dans `docker-compose.yml`, l'utilisateur applicatif garde l'ancien mot de passe tant que le volume n'est pas supprimé.

### Les tests d'intégration sont skippés silencieusement

C'est volontaire. `tests/integration/conftest.py` détecte si MariaDB est inaccessible (`connect_timeout=2`) et exclut le dossier `tests/integration/` de la collection. Lancer `docker compose up -d` puis relancer `pytest -m integration` doit les faire apparaître.

### `RuntimeError: encryption-key secret is missing`

La fonction ne trouve ni le fichier `/var/openfaas/secrets/encryption-key` ni la variable d'env `ENCRYPTION_KEY`. En local :

```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
```

Puis recharger l'env (`source .env` / `Get-Content .env | ...`).

## Build / Docker

### `faas-cli up` échoue avec `denied: requested access to the resource is denied`

Pas authentifié au registre. Pour GHCR :

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u <votre-handle> --password-stdin
```

Le `GITHUB_TOKEN` doit avoir le scope `write:packages`.

### Image trop grosse

L'image Python `slim` + dépendances pèse ~150 Mo. Pour aller plus loin : passer à `python:3.12-alpine` (mais attention aux deps avec extensions C, e.g. `cryptography` nécessite des wheels alpine ou un build long).

## Déploiement Kubernetes

### Le pod MariaDB reste en `Pending`

Probable problème de `StorageClass`. Sur un cluster custom :

```bash
kubectl get sc
# Si aucune n'est marquée (default), créer un PV à la main ou installer local-path-provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### La fonction renvoie 502 / `failed to read upstream`

Le pod de la fonction met du temps à démarrer (cold start). Augmenter les timeouts dans `stack.yml` :

```yaml
environment:
  read_timeout: 60s
  write_timeout: 60s
  exec_timeout: 60s
```

Et côté gateway OpenFaaS, vérifier `gateway.upstreamTimeout` (Helm value).

### Gateway répond `error finding function <name>.openfaas-fn` (404)

OpenFaaS a été installé sans l'**operator** : il tourne en mode REST API et ignore les CRD `Function` créées par le chart `cofrap`.

Vérifier :

```bash
kubectl -n openfaas-fn get functions.openfaas.com
# generate-password   1m       # le CRD existe
kubectl -n openfaas-fn get deployments
# (vide)                       # mais aucun deployment → controller absent
kubectl -n openfaas get deployment gateway -o yaml | grep -i operator
# Si rien → operator pas activé
```

Activer l'operator sur une install existante (sans tout recréer) :

```bash
helm upgrade openfaas openfaas/openfaas \
  --namespace openfaas \
  --reuse-values \
  --set operator.create=true \
  --set operator.createCRD=true \
  --wait
```

Au bout de 10-20 s, les pods des fonctions apparaissent :

```bash
kubectl -n openfaas-fn get pods
# generate-password-xxxx-yyyy    1/1   Running
# generate-2fa-xxxx-yyyy         1/1   Running
# authenticate-user-xxxx-yyyy    1/1   Running
```

Le path correct du healthcheck est `/healthz` (pas `/health`) :

```bash
curl -s http://127.0.0.1:8080/function/generate-password/healthz
# {"status":"ok"}
```

### `pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")`

Le DNS interne du cluster n'est pas joignable depuis le namespace `openfaas-fn`. Vérifier :

```bash
kubectl -n openfaas-fn run debug --rm -it --image=busybox -- sh
# Dans le pod :
nslookup mariadb.cofrap.svc.cluster.local
```

Si la résolution échoue, vérifier que CoreDNS tourne (`kubectl -n kube-system get pods -l k8s-app=kube-dns`).

## API

### `422 Unprocessable Entity` sur toute requête

La validation Pydantic a refusé le payload. La réponse contient le détail :

```json
{"detail": [{"loc": ["body", "otp"], "msg": "String should match pattern '^\\d{6}$'", "type": "string_pattern_mismatch"}]}
```

Vérifier que le `Content-Type: application/json` est bien envoyé et que le JSON est valide.

### Le QR code généré donne un mot de passe illisible / déchiffrement échoue

Vraisemblablement la `ENCRYPTION_KEY` a changé entre le moment de l'insertion et la lecture. Vérifier :

```bash
faas-cli secret list   # date de last update
```

Si la clé a été régénérée par erreur, tous les comptes existants sont à recréer (`generate-password` + `generate-2fa`).

### `authenticate-user` renvoie `expired` alors que le compte vient d'être créé

Vérifier l'horloge du cluster vs le poste client. La fenêtre de validité TOTP est de 30 s ± 1 (cf. `valid_window=1` dans `pyotp.TOTP.verify`). Une dérive d'horloge supérieure à 30 s fait échouer le code TOTP. Causes courantes : VM en pause, NTP non configuré sur les nodes.

## CI GitHub Actions

### Le workflow `release.yml` échoue avec `Resource not accessible by integration`

Permissions GHCR manquantes. Vérifier en haut du workflow :

```yaml
permissions:
  contents: read
  packages: write
```

Et que le repo a bien `Settings → Actions → Workflow permissions: Read and write`.

### Cache Buildx invalidé à chaque run

`cache-from: type=gha,scope=<function>` doit utiliser la même valeur de `scope` entre les runs. Vérifier qu'il n'y a pas de variable interpolée (e.g. `${{ github.run_id }}`) dans le scope.
