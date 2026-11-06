# GitLab CI/CD Pipeline & GitHub GitOps Integration Guide

## 1. End-to-End Delivery Architecture

```
Developer Push (App Code)
        │
        ▼
GitLab CI/CD Pipeline
  ├── 1. validate     (Python py_compile, YAML syntax, Helm lint)
  ├── 2. test         (Pytest unit test suite & JUnit reporting)
  ├── 3. build        (Docker multi-stage build, tag with ${CI_COMMIT_SHORT_SHA})
  ├── 4. publish      (Docker login & push to GitLab Container Registry)
  └── 5. update-gitops (Clone GitHub repo, update values.yaml, commit & push)
        │
        ▼
GitHub Repository (Source of Truth)
  └── helm/gitops-demo/values.yaml (image.tag = ${CI_COMMIT_SHORT_SHA})
        │
        ▼
Argo CD Controller (Reconciliation Engine)
  ├── Detects Git commit revision
  ├── Generates target manifests via Helm
  └── Synchronizes desired state into Kubernetes (gitops-demo namespace)
        │
        ▼
Kubernetes Cluster (Minikube)
  └── Pod running updated version, verified via /health & /version
```

---

## 2. Pipeline Stages & Implementation

| Stage | Job Name | Environment | Action & Responsibilities |
| :--- | :--- | :--- | :--- |
| **`validate`** | `lint-and-validate` | `python:3.12-slim` | Compiles Python code via `py_compile`, verifies raw YAML configs via PyYAML, and lints Helm chart via `helm lint`. |
| **`test`** | `unit-tests` | `python:3.12-slim` | Installs dev dependencies and runs 6-point Pytest suite, exporting `junit-report.xml` test report artifact. |
| **`build`** | `build-image` | `docker:27-cli` + `dind` | Builds unprivileged multi-stage container image, tags with `${CI_COMMIT_SHORT_SHA}`, and archives `image.tar` artifact. |
| **`publish`** | `publish-image` | `docker:27-cli` + `dind` | Authenticates via `${CI_REGISTRY_USER}` and `${CI_REGISTRY_PASSWORD}`, pushes immutable SHA-tagged image and updates `:latest`. |
| **`update-gitops`** | `promote-gitops` | `alpine/git:2.45.2` | Clones GitHub repo with `${GITOPS_GITHUB_TOKEN}`, updates `image.tag` in `values.yaml`, commits, and pushes to `main`. |

---

## 3. GitLab Project & Container Registry Setup

1. **Create Project in GitLab:**
   * Create a repository on [GitLab](https://gitlab.com) (e.g. `gitlab.com/<username>/git-argo`).
   * Add GitLab remote to your repository:
     ```bash
     git remote add gitlab https://gitlab.com/<username>/git-argo.git
     ```
2. **GitLab Container Registry:**
   * Container Registry is enabled by default in GitLab projects under **Deploy > Container Registry**.
   * Predefined variables (`CI_REGISTRY`, `CI_REGISTRY_IMAGE`, `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD`) are auto-injected by GitLab into pipeline jobs.

---

## 4. GitHub Personal Access Token (`GITOPS_GITHUB_TOKEN`)

The pipeline requires write access to the deployment repository on GitHub (`SUPRAVAT001/git-argo`) to update `values.yaml`.

### Generating GitHub Token:
1. Navigate to **GitHub > Settings > Developer settings > Personal access tokens > Fine-grained tokens** (or Tokens Classic).
2. Generate a token:
   * **Name:** `gitlab-ci-gitops-token`
   * **Repository access:** Only select repository `SUPRAVAT001/git-argo`.
   * **Permissions:** `Contents: Read and write`.
3. Copy the generated token (begins with `github_pat_` or `ghp_`).

### Configuring in GitLab:
1. Navigate to your GitLab project: **Settings > CI/CD > Variables > Add variable**.
2. Set properties:
   * **Key:** `GITOPS_GITHUB_TOKEN`
   * **Value:** `<your-github-token>`
   * **Type:** `Variable`
   * **Flags:**
     * [x] **Protect variable** (available to protected branches like `main`)
     * [x] **Mask variable** (prevents token from appearing in job logs)
3. Save variable.

---

## 5. Required GitLab CI/CD Variables

| Variable Name | Managed By | Description | Recommended Setting |
| :--- | :--- | :--- | :--- |
| `CI_REGISTRY` | GitLab System | Container registry endpoint (`registry.gitlab.com`) | Automatic |
| `CI_REGISTRY_IMAGE` | GitLab System | Full path to registry image repository | Automatic |
| `CI_REGISTRY_USER` | GitLab System | Ephemeral job authentication user | Automatic |
| `CI_REGISTRY_PASSWORD` | GitLab System | Ephemeral job authentication token | Automatic |
| `CI_COMMIT_SHORT_SHA` | GitLab System | 8-character commit identifier for immutable tagging | Automatic |
| `GITOPS_GITHUB_TOKEN` | User Defined | GitHub Access Token with `contents: write` | **Masked & Protected** |
| `GITHUB_REPO` | Optional override | Default: `SUPRAVAT001/git-argo` | Plain variable |
| `GITOPS_BRANCH` | Optional override | Default: `main` | Plain variable |

---

## 6. Runner Requirements & Execution

* **GitLab SaaS Shared Runners:** The `.gitlab-ci.yml` pipeline is fully compatible with standard GitLab Linux SaaS runners with Docker-in-Docker support (`docker:dind`).
* **Self-Hosted Runner (Optional):** If running on self-hosted infrastructure, use a Docker-executor runner outside the Minikube cluster to avoid resource contention.
* **Offline Verification:** The pipeline logic can be validated offline at any time using [`scripts/local-ci-simulate.sh`](file:///home/sdash/git-argo/scripts/local-ci-simulate.sh).
