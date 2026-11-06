# GitOps Platform Demonstration Runbook

This runbook outlines the step-by-step procedures to demonstrate and verify the continuous delivery, drift detection, self-healing, and declarative rollback capabilities of the **GitOps CI/CD Platform with Argo CD**.

---

## Architecture Overview

```
Developer Push (Source Code) 
         │
         ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                    GitLab CI/CD Engine                       │
 │  1. validate  ──>  2. test  ──>  3. build  ──>  4. publish   │
 └──────────────────────────────────────┬───────────────────────┘
                                        │
                         Push Image     ▼     GitLab Registry
                     ┌──────────────────────────────────────────┐
                     │  registry.gitlab.com/repo:<commit-sha>   │
                     └──────────────────┬───────────────────────┘
                                        │
                        Stage 5: Update │ GitOps Tag
                                        ▼
 ┌──────────────────────────────────────────────────────────────┐
 │             GitHub Repository (Source of Truth)              │
 │               helm/gitops-demo/values.yaml                   │
 └──────────────────────────────────────┬───────────────────────┘
                                        │
                         Detects Change │ Poll / Webhook
                                        ▼
 ┌──────────────────────────────────────────────────────────────┐
 │             Argo CD Controller (gitops-engine)               │
 │  - Reconciles desired state vs live cluster state            │
 │  - Enforces automated self-healing & drift detection         │
 └──────────────────────────────────────┬───────────────────────┘
                                        │
                         Declarative    ▼     Reconciliation
 ┌──────────────────────────────────────────────────────────────┐
 │               Kubernetes Cluster (Minikube)                  │
 │  - Namespace: gitops-demo                                    │
 │  - Workload: FastAPI Microservice (Non-root, probes, limits) │
 └──────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

* Active Kubernetes cluster (`minikube status` reporting `Ready`).
* Git remote configured to GitHub (`origin` pointing to `git@github.com:SUPRAVAT001/git-argo.git`).
* Argo CD operational in `argocd` namespace.
* Application deployed in `gitops-demo` namespace.

---

## Scenario 1: Baseline Deployment Verification (v1.0.0)

**Objective:** Verify that Argo CD has deployed the initial baseline v1.0.0 application and reconciled it to `Synced` and `Healthy`.

### 1.1 Verify Argo CD Synchronization

```bash
kubectl get application -n argocd gitops-demo
```

**Expected Output:**
```
NAME          SYNC STATUS   HEALTH STATUS
gitops-demo   Synced        Healthy
```

### 1.2 Verify Kubernetes Workload

```bash
kubectl get deployment,pods,svc -n gitops-demo -o wide
```

**Expected Output:**
* Deployment `gitops-demo` reports `1/1` Available.
* Pod reports `Running` with `0` restarts.
* Container image is `gitops-demo:v1.0.0`.

### 1.3 Query Application Runtime Endpoints

```bash
# Query via Minikube container exec or port-forward:
docker exec minikube curl -s http://10.97.72.96:80/version
docker exec minikube curl -s http://10.97.72.96:80/health
```

**Expected Output:**
```json
{"version":"v1.0.0","environment":"production","git_commit":"HEAD","gitops_managed":true,"gitops_tool":"Argo CD"}
{"status":"healthy","timestamp":1793961842.124,"version":"v1.0.0","environment":"production"}
```

---

## Scenario 2: GitOps Version Upgrade (v1.0.0 -> v2.0.0)

**Objective:** Upgrade the microservice to `v2.0.0` by committing declarative changes to Git, allowing Argo CD to automatically detect the change and perform a zero-downtime rolling update.

### 2.1 Update Application and GitOps Manifests

1. Update `app/main.py`: Set `APP_VERSION` default to `"v2.0.0"`.
2. Update `helm/gitops-demo/values.yaml`: Set `image.tag: "v2.0.0"`.
3. Update `helm/gitops-demo/Chart.yaml`: Set `appVersion: "v2.0.0"` and bump `version: 1.1.0`.

### 2.2 Validate and Build Locally

```bash
# Run unit tests
python3 -m pytest app/tests/ -v

# Build and load image into Minikube
docker build --build-arg APP_VERSION=v2.0.0 -t gitops-demo:v2.0.0 -f docker/Dockerfile .
minikube image load gitops-demo:v2.0.0
```

### 2.3 Commit and Push to GitHub

```bash
git add app/ helm/gitops-demo/
git commit -m "feat(app): upgrade application to v2.0.0 and promote GitOps image tag"
git push origin main
```

### 2.4 Verify Automated Synchronization

```bash
# Watch Argo CD detect revision and sync
kubectl get application -n argocd gitops-demo -w

# Verify new pod rollout
kubectl get pods -n gitops-demo -w
```

### 2.5 Query Updated Runtime Endpoints

```bash
docker exec minikube curl -s http://10.97.72.96:80/version
```

**Expected Output:**
```json
{"version":"v2.0.0","environment":"production","git_commit":"HEAD","gitops_managed":true,"gitops_tool":"Argo CD"}
```

---

## Scenario 3: Real-Time Drift Detection and Self-Healing

**Objective:** Inject out-of-band configuration drift into the live Kubernetes cluster and observe Argo CD automatically detect the anomaly and reconcile the cluster back to the Git-defined state.

### 3.1 Inject Configuration Drift

Artificially scale the live deployment to 3 replicas without modifying Git:

```bash
kubectl scale deployment gitops-demo --replicas=3 -n gitops-demo
```

### 3.2 Observe Drift Detection (`OutOfSync`)

Inspect the deployment and Argo CD Application status immediately:

```bash
kubectl get deployment -n gitops-demo
kubectl get application -n argocd gitops-demo
```

**Observed State:**
* Kubernetes deployment scales up to 3 replicas.
* Argo CD transitions `SYNC STATUS` from `Synced` to **`OutOfSync`**.
* Event recorded: `Normal ResourceUpdated Updated sync status: Synced -> OutOfSync`.

### 3.3 Observe Automated Self-Healing Reconciliation

Because `selfHeal: true` is configured in `argocd/application.yaml`, the Argo CD Application Controller immediately intervenes:

```bash
kubectl describe application gitops-demo -n argocd
```

**Observed State:**
* Argo CD initiates automated sync operation: `Auto Heal Attempts Count: 1`.
* Argo CD reapplies desired manifest: `deployment.apps/gitops-demo configured`.
* Kubernetes terminates the 2 unmanaged drift pods.
* Application returns to `Synced` and `Healthy` with exactly 1 replica.

---

## Scenario 4: Git-Based Declarative Rollback

**Objective:** Roll back an active production deployment cleanly via Git without using destructive `kubectl rollout undo` or cluster imperative commands.

### 4.1 Execute Git Revert

```bash
# Revert the promotion commit
git revert HEAD --no-edit

# Push rollback commit to GitHub
git push origin main
```

### 4.2 Observe Argo CD Synchronization

Argo CD detects the new rollback commit in GitHub:

```bash
kubectl get application -n argocd gitops-demo
kubectl get pods -n gitops-demo -w
```

**Observed State:**
* Argo CD detects new commit hash.
* Deployment initiates rolling update from `gitops-demo:v2.0.0` back to `gitops-demo:v1.0.0`.
* The `v2.0.0` pod enters `Terminating` and clean `v1.0.0` pod enters `Running`.

### 4.3 Verify Live Runtime Rollback

```bash
docker exec minikube curl -s http://10.97.72.96:80/version
docker exec minikube curl -s http://10.97.72.96:80/health
```

**Expected Output:**
```json
{"version":"v1.0.0","environment":"production","git_commit":"HEAD","gitops_managed":true,"gitops_tool":"Argo CD"}
```

---

## Scenario 5: Full Operational Platform Health Check

Run a combined verification to ensure all workloads, namespaces, and sibling projects remain healthy:

```bash
# 1. Kubernetes node status
kubectl get nodes -o wide

# 2. GitOps application status
kubectl get all -n gitops-demo
kubectl get application -n argocd

# 3. Argo CD core infrastructure
kubectl get pods -n argocd

# 4. Sibling observability workloads (kube-obs)
kubectl get pods -n observability

# 5. Sibling DevOps Jarvis staging containers
docker ps --filter "name=jarvis"

# 6. WSL2 host memory and swap
free -h
```

---

## Summary of Demonstration Scenarios

| Scenario | Trigger / Action | Mechanism | Argo CD Status | Final Workload Version |
| :--- | :--- | :--- | :--- | :--- |
| **1. Baseline** | Initial Argo CD deployment | Helm chart sync from GitHub | `Synced` / `Healthy` | `v1.0.0` (1 replica) |
| **2. Upgrade** | Push commit `a702fba` (`tag: v2.0.0`) | Automated Git reconciliation | `Synced` / `Healthy` | `v2.0.0` (1 replica) |
| **3. Drift Remediation** | Manual `kubectl scale --replicas=3` | Drift detection + Self-healing | `OutOfSync` -> `Synced` | `v2.0.0` (1 replica) |
| **4. Git Rollback** | Push revert commit `9f8c045` (`tag: v1.0.0`) | Declarative Git rollback | `Synced` / `Healthy` | `v1.0.0` (1 replica) |
| **5. Health Verification** | Cluster-wide non-destructive audit | Platform observability | All Systems Healthy | All Stacks Operational |
