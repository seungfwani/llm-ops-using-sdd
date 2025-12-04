# Argo Workflows Deployment

This directory contains Kubernetes manifests for deploying Argo Workflows.

## Components

- **argo-workflows-controller.yaml**: Argo Workflows controller deployment
- **argo-workflows-server.yaml**: Argo Workflows server (UI) deployment
- **argo-rbac.yaml**: RBAC (Role-Based Access Control) configuration

## Prerequisites

- Kubernetes cluster (v1.20+)
- kubectl configured to access the cluster
- Argo Workflows CRDs installed (see installation section)

## Installation

### 1. Install Argo Workflows CRDs

```bash
kubectl create namespace argo
kubectl apply -n argo -f https://github.com/argoproj/argo-workflows/releases/download/v3.5.5/install.yaml
```

Or install CRDs only:

```bash
kubectl apply -f https://github.com/argoproj/argo-workflows/releases/download/v3.5.5/crds/minimal/base/workflow-crds.yaml
```

### 2. Deploy Argo Workflows Components

```bash
# Apply RBAC first
kubectl apply -f argo-rbac.yaml

# Apply controller
kubectl apply -f argo-workflows-controller.yaml

# Apply server
kubectl apply -f argo-workflows-server.yaml
```

### 3. Verify Installation

```bash
# Check controller status
kubectl get pods -n argo -l app=argo-workflows,component=controller

# Check server status
kubectl get pods -n argo -l app=argo-workflows,component=server

# Check services
kubectl get svc -n argo
```

## Configuration

### Artifact Storage

The controller is configured to use MinIO for artifact storage. Update the ConfigMap in `argo-workflows-controller.yaml` if you need to change the artifact repository configuration.

### Server Access

The Argo Workflows server is exposed via ClusterIP service. To access the UI:

```bash
# Port-forward to local machine
kubectl port-forward -n argo svc/argo-workflows-server 2746:2746

# Access UI at http://localhost:2746
```

## Integration with LLM Ops Platform

The platform uses Argo Workflows through the orchestration adapter (`backend/src/integrations/orchestration/argo_adapter.py`). The adapter communicates with Argo Workflows via Kubernetes API.

### Configuration in Platform Settings

Set the following environment variables:

```bash
WORKFLOW_ORCHESTRATION_ENABLED=true
WORKFLOW_ORCHESTRATION_SYSTEM=argo_workflows
ARGO_WORKFLOWS_NAMESPACE=argo
ARGO_WORKFLOWS_CONTROLLER_SERVICE=argo-workflows-server.argo.svc.cluster.local:2746
```

## Troubleshooting

### Controller Not Starting

```bash
# Check controller logs
kubectl logs -n argo -l app=argo-workflows,component=controller

# Check RBAC permissions
kubectl auth can-i create workflows --as=system:serviceaccount:argo:argo-workflows-controller -n argo
```

### Server Not Accessible

```bash
# Check server logs
kubectl logs -n argo -l app=argo-workflows,component=server

# Verify service endpoints
kubectl get endpoints -n argo argo-workflows-server
```

### Workflows Not Executing

```bash
# Check workflow status
kubectl get workflows -n argo

# Check workflow events
kubectl describe workflow <workflow-name> -n argo

# Check pod status
kubectl get pods -n argo
```

## References

- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [Argo Workflows GitHub](https://github.com/argoproj/argo-workflows)

