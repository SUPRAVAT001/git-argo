#!/usr/bin/env bash
# ==============================================================================
# Local CI/CD Pipeline Simulator for GitOps Platform
# ==============================================================================
# Accurately mirrors the 5-stage GitLab CI/CD pipeline locally:
# 1. validate      - Lints Helm chart, checks Python syntax & YAML structure
# 2. test          - Executes Pytest unit test suite
# 3. build         - Builds unprivileged multi-stage Docker container image
# 4. publish       - Distributes image to local Minikube container cache
# 5. update-gitops - Updates Helm values.yaml image.tag for Argo CD sync
#
# NOTE: This local harness provides deterministic offline verification without
# requiring active GitLab Runner or Container Registry credentials.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CURRENT_SHA="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "local")"
VERSION="${1:-${VERSION:-${CURRENT_SHA}}}"
IMAGE_NAME="gitops-demo"
FULL_IMAGE="${IMAGE_NAME}:${VERSION}"
HELM_VALUES="${REPO_ROOT}/helm/gitops-demo/values.yaml"
VENV_DIR="${REPO_ROOT}/.venv"
HELM_BIN="/home/sdash/.local/bin/helm"

if ! command -v "${HELM_BIN}" >/dev/null 2>&1; then
    HELM_BIN="$(command -v helm || true)"
fi

echo "======================================================================"
echo " Starting Local CI Simulation for ${FULL_IMAGE}"
echo " [NOTICE] Simulating stages defined in .gitlab-ci.yml offline"
echo "======================================================================"

# ------------------------------------------------------------------------------
# STAGE 1: VALIDATE
# ------------------------------------------------------------------------------
echo ""
echo "==> [Stage 1/5: validate] Running static validation & Helm linting..."
python3 -m py_compile "${REPO_ROOT}/app/main.py"
echo "  [OK] Python syntax validation passed"

python3 -c "
import glob, yaml, sys
raw_yaml_files = [f for f in glob.glob('${REPO_ROOT}/helm/**/*.yaml', recursive=True) + glob.glob('${REPO_ROOT}/argocd/*.yaml') if 'templates' not in f]
for f in raw_yaml_files:
    try:
        yaml.safe_load(open(f))
    except Exception as e:
        print(f'YAML parse error in {f}: {e}', file=sys.stderr)
        sys.exit(1)
print(f'  [OK] Successfully validated {len(raw_yaml_files)} raw YAML configuration files')
"

if [ -n "${HELM_BIN}" ] && [ -x "${HELM_BIN}" ]; then
    "${HELM_BIN}" lint "${REPO_ROOT}/helm/gitops-demo"
    echo "  [OK] Helm chart linting passed"
else
    echo "  [WARN] Helm binary not found; skipping helm lint"
fi

# ------------------------------------------------------------------------------
# STAGE 2: TEST
# ------------------------------------------------------------------------------
echo ""
echo "==> [Stage 2/5: test] Running unit test suite with pytest..."
if [ -d "${VENV_DIR}" ]; then
    PYTHONPATH="${REPO_ROOT}" "${VENV_DIR}/bin/pytest" "${REPO_ROOT}/app/tests" -v
else
    PYTHONPATH="${REPO_ROOT}" python3 -m pytest "${REPO_ROOT}/app/tests" -v
fi
echo "  [OK] Unit tests passed"

# ------------------------------------------------------------------------------
# STAGE 3: BUILD
# ------------------------------------------------------------------------------
echo ""
echo "==> [Stage 3/5: build] Building Docker container image: ${FULL_IMAGE}..."
docker build \
    --build-arg APP_VERSION="${VERSION}" \
    -t "${FULL_IMAGE}" \
    -f "${REPO_ROOT}/docker/Dockerfile" \
    "${REPO_ROOT}"
echo "  [OK] Docker image built successfully"

# ------------------------------------------------------------------------------
# STAGE 4: PUBLISH (Local Minikube Distribution)
# ------------------------------------------------------------------------------
echo ""
echo "==> [Stage 4/5: publish] Distributing image into Minikube image cache..."
if command -v minikube >/dev/null 2>&1; then
    minikube image load "${FULL_IMAGE}"
    echo "  [OK] Image ${FULL_IMAGE} loaded into Minikube"
else
    echo "  [WARN] Minikube not found; image exists in local Docker engine only"
fi

# ------------------------------------------------------------------------------
# STAGE 5: UPDATE GITOPS
# ------------------------------------------------------------------------------
echo ""
echo "==> [Stage 5/5: update-gitops] Updating Helm values.yaml image tag to '${VERSION}'..."
if [ -f "${HELM_VALUES}" ]; then
    sed -i -E "s/(tag: \")[^\"]+(\")/\1${VERSION}\2/" "${HELM_VALUES}"
    echo "  [OK] ${HELM_VALUES} updated to tag: \"${VERSION}\""
    echo ""
    echo "GitOps Configuration Diff:"
    git -C "${REPO_ROOT}" diff "${HELM_VALUES}" || true
else
    echo "  [ERROR] values.yaml not found at ${HELM_VALUES}"
    exit 1
fi

echo ""
echo "======================================================================"
echo " [SUCCESS] Local CI Pipeline completed successfully for ${VERSION}"
echo "======================================================================"
