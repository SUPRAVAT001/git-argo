import pytest
from fastapi.testclient import TestClient
from app.main import app, REQUEST_COUNTS, APP_VERSION

client = TestClient(app)


def test_landing_html():
    """Verify landing page returns HTML with key GitOps metadata."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GitOps CI/CD Platform Demo" in response.text or "gitops-demo-app" in response.text
    assert "Argo CD" in response.text
    assert "Observability &amp; Telemetry Endpoints" in response.text or "Observability & Telemetry Endpoints" in response.text
    assert "/health" in response.text
    assert "/version" in response.text
    assert "/metrics" in response.text


def test_landing_json_negotiation():
    """Verify landing page supports JSON content negotiation when requested."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert data["application"] == "gitops-demo-app"
    assert data["gitops_tool"] == "Argo CD"
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


def test_health_endpoint():
    """Verify health check endpoint returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data
    assert "environment" in data


def test_version_endpoint():
    """Verify version endpoint exposes application version and GitOps metadata."""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == APP_VERSION
    assert data["gitops_managed"] is True
    assert data["gitops_tool"] == "Argo CD"
    assert "environment" in data
    assert "git_commit" in data


def test_metrics_endpoint():
    """Verify metrics endpoint exposes Prometheus-formatted telemetry."""
    # Generate some traffic first
    client.get("/health")
    client.get("/version")

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text

    # Verify Prometheus metric types and gauges
    assert "# HELP app_uptime_seconds Application uptime in seconds." in body
    assert "# TYPE app_uptime_seconds gauge" in body
    assert "app_uptime_seconds" in body

    assert "# HELP app_info Application version and metadata." in body
    assert "# TYPE app_info gauge" in body
    assert f'app_info{{version="{APP_VERSION}"' in body

    assert "# HELP app_http_requests_total Total number of HTTP requests processed by endpoint and status." in body
    assert "# TYPE app_http_requests_total counter" in body
    assert 'app_http_requests_total{method="GET",endpoint="/health",status="200"}' in body


def test_metrics_counting():
    """Verify middleware accurately tracks request counts per endpoint."""
    initial_count = REQUEST_COUNTS.get("GET:/version:200", 0)
    client.get("/version")
    new_count = REQUEST_COUNTS.get("GET:/version:200", 0)
    assert new_count == initial_count + 1

