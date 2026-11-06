import os
import time
from typing import Dict
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

APP_NAME = os.getenv("APP_NAME", "gitops-demo-app")
APP_VERSION = os.getenv("APP_VERSION", "v2.0.0")
APP_ENV = os.getenv("APP_ENV", "production")
GIT_COMMIT = os.getenv("GIT_COMMIT", "HEAD")
GITOPS_TOOL = os.getenv("GITOPS_TOOL", "Argo CD")

START_TIME = time.time()
REQUEST_COUNTS: Dict[str, int] = {}

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="GitOps CI/CD Platform Demo Application",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@app.middleware("http")
async def track_metrics(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    response = await call_next(request)
    status_code = response.status_code

    key = f'{method}:{endpoint}:{status_code}'
    REQUEST_COUNTS[key] = REQUEST_COUNTS.get(key, 0) + 1
    return response


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    # Check if client explicitly asks for JSON
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header and "text/html" not in accept_header:
        return JSONResponse({
            "application": APP_NAME,
            "version": APP_VERSION,
            "environment": APP_ENV,
            "git_commit": GIT_COMMIT,
            "gitops_tool": GITOPS_TOOL,
            "uptime_seconds": round(time.time() - START_TIME, 2),
            "status": "healthy",
        })

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{APP_NAME} - {APP_VERSION}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #38bdf8;
            --accent: #10b981;
            --border: #334155;
            --badge-bg: #0369a1;
        }}
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: radial-gradient(circle at top right, #1e1b4b, var(--bg-color));
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 680px;
            margin: 20px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
            overflow: hidden;
        }}
        .header {{
            padding: 32px 32px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .title-group h1 {{
            margin: 0 0 6px;
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.025em;
        }}
        .title-group p {{
            margin: 0;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
        .version-badge {{
            background: var(--badge-bg);
            color: #e0f2fe;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.35);
        }}
        .content {{
            padding: 28px 32px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
        }}
        .card-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }}
        .card-value {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-main);
        }}
        .card-value.accent {{
            color: var(--accent);
        }}
        .endpoints {{
            margin-top: 16px;
            border-top: 1px solid var(--border);
            padding-top: 20px;
        }}
        .endpoints h3 {{
            margin: 0 0 12px;
            font-size: 0.875rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .endpoint-links {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .endpoint-link {{
            background: #334155;
            color: #e2e8f0;
            text-decoration: none;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 0.8125rem;
            font-family: monospace;
            transition: all 0.15s ease-in-out;
        }}
        .endpoint-link:hover {{
            background: var(--primary);
            color: #0f172a;
        }}
        .footer {{
            padding: 16px 32px;
            background: #090d16;
            border-top: 1px solid var(--border);
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title-group">
                <h1>{APP_NAME}</h1>
                <p>Enterprise GitOps Continuous Delivery Platform</p>
            </div>
            <span class="version-badge">{APP_VERSION}</span>
        </div>
        <div class="content">
            <div class="grid">
                <div class="card">
                    <div class="card-label">Deployment Environment</div>
                    <div class="card-value">{APP_ENV}</div>
                </div>
                <div class="card">
                    <div class="card-label">Continuous Delivery Engine</div>
                    <div class="card-value accent">{GITOPS_TOOL}</div>
                </div>
                <div class="card">
                    <div class="card-label">Git Revision</div>
                    <div class="card-value" style="font-family: monospace;">{GIT_COMMIT[:10]}</div>
                </div>
                <div class="card">
                    <div class="card-label">Cluster Status</div>
                    <div class="card-value accent">Synchronized & Healthy</div>
                </div>
            </div>
            <div class="endpoints">
                <h3>Observability & Telemetry Endpoints</h3>
                <div class="endpoint-links">
                    <a class="endpoint-link" href="/health">/health</a>
                    <a class="endpoint-link" href="/version">/version</a>
                    <a class="endpoint-link" href="/metrics">/metrics</a>
                    <a class="endpoint-link" href="/docs">/docs (OpenAPI)</a>
                </div>
            </div>
        </div>
        <div class="footer">
            <span>Orchestrated via Kubernetes & Helm</span>
            <span>Uptime: {round(time.time() - START_TIME, 1)}s</span>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": APP_VERSION,
        "environment": APP_ENV,
    }


@app.get("/version")
async def version():
    return {
        "version": APP_VERSION,
        "environment": APP_ENV,
        "git_commit": GIT_COMMIT,
        "gitops_managed": True,
        "gitops_tool": GITOPS_TOOL,
    }


@app.get("/metrics")
async def metrics():
    uptime = time.time() - START_TIME

    lines = [
        "# HELP app_uptime_seconds Application uptime in seconds.",
        "# TYPE app_uptime_seconds gauge",
        f"app_uptime_seconds {uptime:.2f}",
        "",
        "# HELP app_info Application version and metadata.",
        "# TYPE app_info gauge",
        f'app_info{{version="{APP_VERSION}",environment="{APP_ENV}",tool="{GITOPS_TOOL}"}} 1',
        "",
        "# HELP app_http_requests_total Total number of HTTP requests processed by endpoint and status.",
        "# TYPE app_http_requests_total counter",
    ]

    for key, count in REQUEST_COUNTS.items():
        parts = key.split(":")
        if len(parts) == 3:
            method, endpoint, status = parts
            lines.append(f'app_http_requests_total{{method="{method}",endpoint="{endpoint}",status="{status}"}} {count}')

    lines.append("")
    return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4; charset=utf-8")

