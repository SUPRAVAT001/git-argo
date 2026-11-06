# Enterprise GitOps CI/CD Delivery Platform with Argo CD

![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.35.1-326CE5?logo=kubernetes&logoColor=white)
![Argo CD](https://img.shields.io/badge/Argo%20CD-v3.6.1-EF7B4D?logo=argo&logoColor=white)
![GitLab CI](https://img.shields.io/badge/GitLab%20CI%2FCD-Pipeline%20Ready-FC6D26?logo=gitlab&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-v3.22.1-0F1689?logo=helm&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Multi--stage%20Unprivileged-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Apache%202.0-green)

A production-grade, demonstrable GitOps Continuous Delivery platform integrating **GitLab CI/CD**, **GitHub**, **Argo CD**, **Helm**, and **Kubernetes**. 

Implements an automated delivery workflow: application code changes trigger static validation and unit tests, build and publish immutable container images, update declarative GitOps manifests in GitHub, and automatically synchronize Kubernetes deployments via Argo CD with continuous drift detection and self-healing.

---

## 1. Architectural Workflow

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

## 2. Key Capabilities

* **Immutable Commit SHA Tagging**: Replaces mutable `latest` tags with deterministic git commit SHAs (`${CI_COMMIT_SHORT_SHA}`) across build, publish, and Helm values.
* **Declarative GitOps Delivery**: Argo CD manages application lifecycle strictly from Git configuration; manual cluster modifications (drift) are automatically detected and self-healed.
* **Separation of Concerns**: GitLab manages CI/CD validation and container publishing; GitHub remains the immutable source of truth for deployment manifests.
* **Unprivileged Container Security**: Multi-stage Docker builds running as non-root user `appuser` (UID 10001, GID 10001) with Linux capability stripping (`drop: [ALL]`).
* **Resource Optimization**: Tuned for dense local environments (WSL2 / Minikube) alongside existing production workloads (`kube-obs`), utilizing strict resource requests (`50m` CPU, `64Mi` RAM) and limits (`200m` CPU, `128Mi` RAM).
* **Dual-Mode Verification**: Supports deterministic local pipeline simulation ([`scripts/local-ci-simulate.sh`](file:///home/sdash/git-argo/scripts/local-ci-simulate.sh)) for offline evaluation, alongside enterprise `.gitlab-ci.yml` cloud pipelines.

---

## 3. Repository Structure

```
git-argo/
├── app/
│   ├── main.py                  # FastAPI microservice (/, /health, /version, /metrics)
│   ├── requirements.txt         # Production runtime dependencies
│   ├── requirements-dev.txt     # Test & development dependencies
│   └── tests/
│       ├── __init__.py
│       └── test_main.py         # 6-point Pytest validation suite
├── docker/
│   └── Dockerfile               # Multi-stage unprivileged container specification
├── helm/
│   └── gitops-demo/
│       ├── Chart.yaml           # Helm chart definition (v1.0.0)
│       ├── values.yaml          # Declarative configuration defaults
│       └── templates/
│           ├── _helpers.tpl     # Standard naming and label helpers
│           ├── deployment.yaml  # Workload deployment with probes and securityContext
│           ├── service.yaml     # ClusterIP service exposing port 80 -> 8080
│           ├── configmap.yaml   # Decoupled environment variables
│           ├── serviceaccount.yaml # Non-root ServiceAccount (token automount disabled)
│           └── ingress.yaml     # Optional NGINX ingress route
├── argocd/
│   ├── application.yaml         # Argo CD Application Custom Resource (Automated + Self-heal)
│   └── argocd-values.yaml       # Lean Argo CD configuration for constrained nodes
├── docs/
│   ├── argocd-guide.md          # Argo CD deployment, access, and troubleshooting
│   └── gitlab-ci.md             # GitLab pipeline configuration & GitHub token setup
├── scripts/
│   └── local-ci-simulate.sh     # Offline 5-stage CI/CD pipeline simulation harness
├── .gitlab-ci.yml               # Production 5-stage GitLab CI/CD pipeline definition
├── .dockerignore                # Build context exclusion rules
├── .gitignore                   # Credential, cache, and virtual environment hygiene
├── pytest.ini                   # Pytest runner configuration
└── README.md                    # Project documentation
```

---

## 4. Application Endpoints & Telemetry

The application provides essential cloud-native endpoints:

| Endpoint | Method | Format | Description |
| :--- | :--- | :--- | :--- |
| **`/`** | `GET` | HTML / JSON | Modern landing page displaying application metadata, active version, environment, and GitOps sync state. |
| **`/health`** | `GET` | JSON | Kubernetes liveness and readiness probe endpoint (`200 OK`). |
| **`/version`** | `GET` | JSON | Deployed version (`v1.0.0`), git commit reference, and GitOps engine attribution. |
| **`/metrics`** | `GET` | Plaintext | Prometheus TSDB metrics (`app_uptime_seconds`, `app_info`, `app_http_requests_total`). |
| **`/docs`** | `GET` | HTML | Interactive OpenAPI documentation and API explorer. |

---

## 5. GitLab CI/CD Pipeline Specifications

The pipeline ([`.gitlab-ci.yml`](file:///home/sdash/git-argo/.gitlab-ci.yml)) executes five sequential stages:

1. **`validate` (`lint-and-validate`)**: Runs Python static compilation check (`py_compile`), verifies YAML manifest syntax, and executes `helm lint`.
2. **`test` (`unit-tests`)**: Runs the Pytest suite, exporting test execution reports as JUnit XML artifacts.
3. **`build` (`build-image`)**: Builds the Docker container via Docker-in-Docker, tagging with `${CI_COMMIT_SHORT_SHA}`, and packages `image.tar`.
4. **`publish` (`publish-image`)**: Authenticates to GitLab Container Registry (`CI_REGISTRY`) and pushes the verified immutable image tag and latest alias.
5. **`update-gitops` (`promote-gitops`)**: Clones the GitHub repository using `${GITOPS_GITHUB_TOKEN}`, updates `helm/gitops-demo/values.yaml` image tag, commits with `[skip ci]`, and pushes to `main`.

### Required CI/CD Variables

Configure in **GitLab > Settings > CI/CD > Variables**:
* `GITOPS_GITHUB_TOKEN`: GitHub Personal Access Token (`contents: write`) — **Masked & Protected**.
* `GITHUB_REPO`: `SUPRAVAT001/git-argo` (default).
* `GITOPS_BRANCH`: `main` (default).

---

## 6. Local Pipeline Simulation

Run the offline CI simulation harness:

```bash
# Execute local pipeline for version v1.0.0
./scripts/local-ci-simulate.sh v1.0.0

# Or execute with current Git short SHA
./scripts/local-ci-simulate.sh $(git rev-parse --short HEAD)
```

The script runs all 5 pipeline stages offline (validation, Pytest execution, Docker build, Minikube image cache distribution, and Helm values update).

---

## 7. Argo CD Access & Operations

```bash
# 1. Forward Argo CD web interface to localhost:8085
kubectl port-forward svc/argocd-server -n argocd 8085:443 --address 127.0.0.1

# 2. Retrieve initial admin password securely from Kubernetes:
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo ""

# 3. Access in browser:
https://localhost:8085 (Username: admin)
```

---

## 8. Verification & Status Distinction

* **Locally Verified & Live**:
  * Minikube Kubernetes cluster running v1.35.1 in `Ready` state.
  * Sibling workloads (`kube-obs` Prometheus/Grafana and `devops-jarvis`) verified healthy.
  * Argo CD installed in `argocd` namespace reporting **`Synced`** and **`Healthy`**.
  * Microservice running in `gitops-demo` serving `/health`, `/version` (`v1.0.0`), and `/metrics`.
  * Local 5-stage simulation harness tested and passing 100%.
  * Version promotion (v1.0.0 -> v2.0.0), drift detection, self-healing, and Git-based rollback verified live.
* **Configured for Hosted GitLab CI**:
  * `.gitlab-ci.yml` authored and verified according to enterprise GitLab CI/CD specifications.
  * Hosted pipeline execution awaits remote GitLab repository connection and token configuration (`GITOPS_GITHUB_TOKEN`).
  * No external cloud runs fabricated; local simulations and Kubernetes cluster synchronizations reflect genuine execution.

---

## 9. Platform Demonstration Scenarios

The platform's continuous delivery, reconciliation, self-healing, and rollback mechanisms have been rigorously demonstrated across five structured scenarios. Complete execution commands and instructions are documented in the [Demonstration Runbook](file:///home/sdash/git-argo/docs/demonstration-runbook.md).

### Scenario Overview Matrix

| Scenario | Objective | Mechanism | Argo CD Status | Deployed Version |
| :--- | :--- | :--- | :--- | :--- |
| **1. Baseline Deployment** | Initial v1.0.0 release verification | Automated Git reconciliation | `Synced` / `Healthy` | `v1.0.0` (1 replica) |
| **2. Version Promotion** | Upgrade microservice to v2.0.0 | Commit `a702fba` pushed to GitHub | `Synced` / `Healthy` | `v2.0.0` (1 replica) |
| **3. Drift & Self-Healing** | Detect manual replica tampering & auto-remediate | `selfHeal: true` controller intervention | `OutOfSync` ➔ `Synced` | `v2.0.0` (1 replica) |
| **4. Declarative Rollback** | Downgrade cleanly via Git revert | Commit `9f8c045` pushed to GitHub | `Synced` / `Healthy` | `v1.0.0` (1 replica) |
| **5. Full Health Audit** | End-to-end cluster & sibling integrity check | Non-destructive telemetry inspection | All Systems Healthy | All Stacks Operational |

### Key Architectural Behaviors Demonstrated

1. **Continuous Drift Detection & Self-Healing:**
   * When `kubectl scale deployment gitops-demo --replicas=3` was executed out-of-band, Argo CD detected configuration drift immediately, flagging the application as `OutOfSync`.
   * Within seconds, the Argo CD Application Controller enforced the Git desired state (`replicas: 1`), terminated the unauthorized pods, and restored the application to `Synced` and `Healthy` (`Auto Heal Attempts Count: 1`).
2. **Declarative Git-Driven Rollback:**
   * Rather than utilizing imperative cluster commands (`kubectl rollout undo`), rollback was executed purely through Git (`git revert a702fba`), restoring `helm/gitops-demo/values.yaml` `image.tag` to `v1.0.0`.
   * Argo CD detected the commit on `origin/main`, initiated a zero-downtime rolling update, and seamlessly restored `v1.0.0` in Kubernetes.

---

## 10. Demonstration Evidence & Screenshots

Authentic, high-resolution PNG terminal screenshots capturing each phase of the demonstration are archived in the [`screenshots/`](file:///home/sdash/git-argo/screenshots/) directory:

| Screenshot | Description & Evidence Captured | File Link |
| :--- | :--- | :--- |
| **01** | **Argo CD Synced & Healthy (v1.0.0)**: Initial deployment status, Helm release, and single healthy pod. | [`01_argocd_synced_healthy_v1.png`](file:///home/sdash/git-argo/screenshots/01_argocd_synced_healthy_v1.png) |
| **02** | **Application v1.0.0 Endpoints**: Live HTTP response bodies for `/version`, `/health`, and Prometheus `/metrics`. | [`02_application_v1_endpoint.png`](file:///home/sdash/git-argo/screenshots/02_application_v1_endpoint.png) |
| **03** | **GitOps Version Promotion (v2.0.0)**: Git diff, Argo CD sync to commit `a702fba`, and `/version` returning `v2.0.0`. | [`03_application_v2_endpoint.png`](file:///home/sdash/git-argo/screenshots/03_application_v2_endpoint.png) |
| **04** | **Argo CD Drift Detection**: Live cluster scaled to 3 replicas, triggering `OutOfSync` detection in Argo CD. | [`04_argocd_drift_detected.png`](file:///home/sdash/git-argo/screenshots/04_argocd_drift_detected.png) |
| **05** | **Argo CD Automated Self-Healing**: Event log capturing automated remediation and termination of drift pods. | [`05_argocd_self_healing.png`](file:///home/sdash/git-argo/screenshots/05_argocd_self_healing.png) |
| **06** | **Git-Based Declarative Rollback**: Revert commit `9f8c045`, Helm values diff, and live downgrade back to `v1.0.0`. | [`06_gitops_git_rollback.png`](file:///home/sdash/git-argo/screenshots/06_gitops_git_rollback.png) |
| **07** | **Final Kubernetes & Sibling Status**: Cluster nodes, Argo CD pods, microservice pod, and Jarvis containers all healthy. | [`07_final_kubernetes_status.png`](file:///home/sdash/git-argo/screenshots/07_final_kubernetes_status.png) |

