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

### Fonctions en `ErrImagePull` / `ImagePullBackOff`

Les images `ghcr.io/cofrap-epsi-2026/<function>:2026.1.2` ne sont publiées que sur **tag git `v*.*.*`** (via le workflow [`release.yml`](../../.github/workflows/release.yml)). Sur un fork ou avant de pousser un tag, ces images n'existent pas → ImagePullBackOff au démarrage des pods.

Builder localement et charger dans le cluster :

```bash
# Linux / WSL / Git Bash
./scripts/build-images.sh

# Windows PowerShell
./scripts/build-images.ps1
```

Le script auto-détecte minikube / K3s / K3d / KinD et utilise le bon mécanisme (`docker-env` pour minikube, `k3s ctr images import` pour K3s, `kind load`, etc.).

Puis appliquer la nouvelle image policy :

```bash
helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.pullPolicy=IfNotPresent
kubectl -n openfaas-fn rollout restart deployment -l 'faas_function'
```

Pour un cluster distant, push sur ton propre registry :

```bash
REGISTRY=ghcr.io/mon-org PUSH=1 ./scripts/build-images.sh
# puis
helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.registry=ghcr.io/mon-org
```

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

Les fonctions ne sont pas découvertes par le gateway. En OpenFaaS Community, la découverte se fait via des Deployments + Services dans `openfaas-fn` labellisés `faas_function=<name>`.

Vérifier la présence des ressources :

```bash
kubectl -n openfaas-fn get deploy,svc,pods -l 'faas_function'
# Si vide → le chart cofrap n'a pas été (correctement) appliqué.
```

Re-déployer le chart :

```bash
./scripts/install.sh                     # Linux / WSL / Git Bash
./scripts/install.ps1                    # Windows PowerShell

# ou directement :
helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --reuse-values --wait
```

Une fois les pods `Running`, le gateway les liste automatiquement :

```bash
PASSWORD=$(kubectl -n openfaas get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d)
curl -s -u admin:$PASSWORD http://127.0.0.1:8080/system/functions | jq '.[].name'
# "generate-password"
# "generate-2fa"
# "authenticate-user"
```

> **Path du healthcheck** : c'est `/healthz` (avec `z`, défini côté FastAPI), pas `/health`. Et le mount path of-watchdog interne `/_/health` est exposé en interne pour les probes K8s, pas via le gateway.

```bash
curl -s http://127.0.0.1:8080/function/generate-password/healthz
# {"status":"ok"}
```

### Erreur Helm `enabling 'operator.create' is only supported for OpenFaaS Pro`

L'option `operator.create=true` du chart `openfaas/openfaas` est réservée à la version Pro. **Ne pas la passer en Community.**

Le chart `cofrap` ne dépend pas de l'operator — il déploie les fonctions comme des Deployments K8s classiques avec le label `faas_function=<name>`, mécanisme natif du gateway Community.

Si un précédent `helm upgrade ... --set operator.create=true` a échoué, l'install OpenFaaS précédente est intacte. Pour réinstaller proprement les fonctions, il suffit de relancer le script :

```bash
./scripts/install.sh -SkipOpenFaaS    # Windows: ./scripts/install.ps1 -SkipOpenFaaS
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
