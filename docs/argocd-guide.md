# Argo CD GitOps Architecture & Operational Guide

## 1. Overview & Architecture

The GitOps delivery model relies on declarative desired state stored in Git and continuously reconciled into Kubernetes by Argo CD. To maintain stability alongside pre-existing workloads (`kube-obs`), Argo CD is provisioned with a tuned, resource-conserving footprint:

* **Application Controller**: Reconciles cluster state against Git manifests.
* **Repo Server**: Clones Git repositories and generates target Kubernetes manifests via Helm.
* **API Server / Web UI**: Exposes gRPC and REST APIs and the management web interface.
* **Redis**: In-memory cache for repository states and cluster object status.
* **Disabled Components**: Dex SSO, Notifications Controller, and ApplicationSet Controller are disabled to reduce memory footprint by ~180 MiB.

---

## 2. Component Resource Allocations

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
| :--- | :--- | :--- | :--- | :--- |
| `argocd-server` | `50m` | `250m` | `64Mi` | `128Mi` |
| `argocd-repo-server` | `50m` | `250m` | `64Mi` | `128Mi` |
| `argocd-application-controller` | `100m` | `300m` | `128Mi` | `256Mi` |
| `argocd-redis` | `20m` | `100m` | `32Mi` | `64Mi` |
| **Total** | **220m** | **900m** | **288Mi** | **576Mi** |

---

## 3. Argo CD Access Instructions

### A. Port-Forwarding Web UI
Argo CD API server runs with insecure HTTP enabled inside the container for local forwarding:

```bash
kubectl port-forward svc/argocd-server -n argocd 8085:80
```

Access in your browser at:
`http://localhost:8085`

### B. Admin Credentials Retrieval
The initial administrative password is automatically generated during installation and stored securely in a Kubernetes secret:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo ""
```

* **Username**: `admin`
* **Password**: Retrieved securely via the above command (never committed to Git).

---

## 4. GitOps Application Specification

The application is registered using the `Application` custom resource definition:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: gitops-demo
  namespace: argocd
  labels:
    app.kubernetes.io/name: gitops-demo
    app.kubernetes.io/part-of: gitops-platform
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/SUPRAVAT001/git-argo.git
    targetRevision: main
    path: helm/gitops-demo
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: gitops-demo
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ApplyOutOfSyncOnly=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

---

## 5. Troubleshooting & Operations

### Check Sync & Health Status via CLI
```bash
# Get Application status
kubectl get application gitops-demo -n argocd -o yaml

# Inspect Argo CD controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller --tail=50
```

### Self-Healing & Drift Detection
* When manual changes occur in `gitops-demo` (e.g. replica count modified via `kubectl scale`), the controller detects the deviation from Git desired state within seconds.
* With `selfHeal: true`, Argo CD automatically reconciles the deployment back to the Git-defined specification.

