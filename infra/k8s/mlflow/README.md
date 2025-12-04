# MLflow Tracking Server Deployment

This directory contains Kubernetes manifests for deploying MLflow Tracking Server.

## Prerequisites

1. PostgreSQL database (deployed in `llm-ops-dev` namespace)
2. MinIO/S3 object storage (deployed in `llm-ops-dev` namespace)
3. Kubernetes cluster with persistent volume support

## Deployment

### 1. Create MLflow namespace and resources

```bash
# Apply all manifests
kubectl apply -f infra/k8s/mlflow/mlflow-configmap.yaml
kubectl apply -f infra/k8s/mlflow/mlflow-secret.yaml
kubectl apply -f infra/k8s/mlflow/mlflow-server.yaml
```

Or apply all at once:

```bash
kubectl apply -f infra/k8s/mlflow/
```

### 2. Verify deployment

```bash
# Check namespace
kubectl get namespace mlflow

# Check pods
kubectl get pods -n mlflow

# Check service
kubectl get svc -n mlflow

# Check logs
kubectl logs -n mlflow deployment/mlflow-server
```

### 3. Initialize MLflow database

Before using MLflow, you need to create the MLflow database schema in PostgreSQL:

```bash
# Connect to PostgreSQL
kubectl exec -it -n llm-ops-dev deployment/postgresql -- psql -U llmops -d llmops

# Create MLflow database
CREATE DATABASE mlflow;

# Exit psql
\q

# Initialize MLflow schema (run from MLflow pod or locally with mlflow installed)
kubectl exec -it -n mlflow deployment/mlflow-server -- \
  mlflow db upgrade --backend-store-uri postgresql://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/mlflow
```

### 4. Create MinIO bucket for MLflow artifacts

```bash
# Create bucket using MinIO client or API
kubectl exec -it -n llm-ops-dev deployment/minio -- \
  mc alias set minio http://localhost:9000 llmops llmops-secret

kubectl exec -it -n llm-ops-dev deployment/minio -- \
  mc mb minio/mlflow-artifacts
```

## Configuration

### Backend Configuration

The MLflow configuration is stored in ConfigMap (`mlflow-config`) and Secret (`mlflow-secret`).

**ConfigMap keys:**
- `MLFLOW_BACKEND_STORE_URI`: PostgreSQL connection string
- `MLFLOW_DEFAULT_ARTIFACT_ROOT`: S3/MinIO bucket path
- `AWS_ENDPOINT_URL`: MinIO endpoint URL
- `MLFLOW_HOST`: Server host (default: 0.0.0.0)
- `MLFLOW_PORT`: Server port (default: 5000)
- `MLFLOW_CORS_ALLOW_ORIGINS`: CORS origins (default: *)

**Secret keys:**
- `AWS_ACCESS_KEY_ID`: MinIO access key
- `AWS_SECRET_ACCESS_KEY`: MinIO secret key
- `POSTGRES_USER`: PostgreSQL username
- `POSTGRES_PASSWORD`: PostgreSQL password
- `POSTGRES_DB`: PostgreSQL database name

### Platform Integration

Update `backend/.env` with MLflow configuration:

```bash
MLFLOW_TRACKING_URI=http://mlflow-service.mlflow.svc.cluster.local:5000
MLFLOW_ENABLED=true
MLFLOW_BACKEND_STORE_URI=postgresql://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/mlflow
MLFLOW_DEFAULT_ARTIFACT_ROOT=s3://mlflow-artifacts/
```

## Access MLflow UI

### Port-forward (local development)

```bash
kubectl port-forward -n mlflow svc/mlflow-service 5000:5000
```

Then open browser: http://localhost:5000

### Ingress (production)

For production, configure an Ingress resource to expose MLflow UI:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mlflow-ingress
  namespace: mlflow
spec:
  rules:
  - host: mlflow.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mlflow-service
            port:
              number: 5000
```

## Troubleshooting

### Check MLflow server logs

```bash
kubectl logs -n mlflow deployment/mlflow-server -f
```

### Verify database connection

```bash
kubectl exec -it -n mlflow deployment/mlflow-server -- \
  psql postgresql://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/mlflow -c "SELECT 1"
```

### Verify S3/MinIO connection

```bash
kubectl exec -it -n mlflow deployment/mlflow-server -- \
  aws --endpoint-url http://minio.llm-ops-dev.svc.cluster.local:9000 s3 ls s3://mlflow-artifacts/
```

### Check service endpoints

```bash
kubectl get endpoints -n mlflow mlflow-service
```

## Scaling

MLflow Tracking Server can be scaled horizontally, but note:
- Backend store (PostgreSQL) handles concurrency
- Artifact storage (S3/MinIO) is shared
- Session affinity is configured for consistent routing

To scale:

```bash
kubectl scale deployment/mlflow-server -n mlflow --replicas=3
```

## Backup and Recovery

### Backup MLflow database

```bash
kubectl exec -it -n llm-ops-dev deployment/postgresql -- \
  pg_dump -U llmops mlflow > mlflow-backup.sql
```

### Backup MLflow artifacts

```bash
# Use MinIO client or S3 tools to backup mlflow-artifacts bucket
kubectl exec -it -n llm-ops-dev deployment/minio -- \
  mc mirror minio/mlflow-artifacts /backup/mlflow-artifacts
```

## Security Considerations

1. **Secrets**: Update `mlflow-secret.yaml` with strong passwords in production
2. **Network Policies**: Configure network policies to restrict access
3. **RBAC**: Use Kubernetes RBAC to control access to MLflow resources
4. **TLS**: Enable TLS for production deployments
5. **Authentication**: Consider adding authentication layer (e.g., OAuth) for MLflow UI

