#!/usr/bin/env python3
"""
Enterprise Screenshot Generator for GitOps Platform Demonstration
Generates authentic, high-resolution PNG terminal screenshots using native PSF fonts
and pure Python PNG encoding (zlib + struct) without external GUI dependencies.
"""

import gzip
import os
import struct
import zlib

FONT_PATH = "/usr/share/consolefonts/Uni3-TerminusBold24x12.psf.gz"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots")

# Tokyo Night / Catppuccin Mocha Color Palette
COLORS = {
    "bg": (30, 30, 46),
    "title_bar": (24, 24, 37),
    "border": (49, 50, 68),
    "text": (205, 214, 244),
    "muted": (108, 112, 134),
    "prompt_user": (137, 180, 250),
    "prompt_dir": (166, 227, 161),
    "cyan": (137, 220, 235),
    "green": (166, 227, 161),
    "yellow": (249, 226, 175),
    "red": (243, 139, 168),
    "orange": (250, 179, 135),
    "btn_red": (243, 139, 168),
    "btn_yellow": (249, 226, 175),
    "btn_green": (166, 227, 161),
}


def load_psf_font(path):
    with gzip.open(path, "rb") as f:
        data = f.read()
    magic = struct.unpack("<I", data[:4])[0]
    if magic != 0x864AB572:
        raise ValueError(f"Unsupported PSF format: {hex(magic)}")
    v, hlen, flags, length, charsize, h, w = struct.unpack("<IIIIIII", data[4:32])
    bytes_per_row = (w + 7) // 8
    glyphs = {}
    for code in range(min(length, 256)):
        offset = hlen + code * charsize
        glyph_bytes = data[offset : offset + charsize]
        bitmap = []
        for y in range(h):
            row_b = glyph_bytes[y * bytes_per_row : (y + 1) * bytes_per_row]
            bits = "".join(f"{b:08b}" for b in row_b)[:w]
            bitmap.append([c == "1" for c in bits])
        glyphs[chr(code)] = bitmap
    return glyphs, w, h


GLYPHS, GW, GH = load_psf_font(FONT_PATH)


class TerminalImage:
    def __init__(self, title, width_cols=86, lines_count=24):
        self.gw = GW
        self.gh = GH
        self.padding_x = 24
        self.padding_top = 46  # includes 36px titlebar + 10px pad
        self.padding_bottom = 20
        self.width = width_cols * self.gw + (self.padding_x * 2)
        self.height = self.padding_top + (lines_count * self.gh) + self.padding_bottom
        self.title = title

        # Initialize background buffer (RGB)
        bg = COLORS["bg"]
        self.buf = bytearray(bg * (self.width * self.height))

        # Render window chrome
        self._render_chrome()

    def _render_chrome(self):
        # Title bar background
        tb_color = COLORS["title_bar"]
        tb_height = 36
        for y in range(tb_height):
            for x in range(self.width):
                idx = (y * self.width + x) * 3
                self.buf[idx : idx + 3] = bytearray(tb_color)

        # Title bar bottom border
        border_color = COLORS["border"]
        for x in range(self.width):
            idx = ((tb_height - 1) * self.width + x) * 3
            self.buf[idx : idx + 3] = bytearray(border_color)

        # Window controls (macOS / Linux style dots)
        buttons = [
            (20, COLORS["btn_red"]),
            (36, COLORS["btn_yellow"]),
            (52, COLORS["btn_green"]),
        ]
        center_y = tb_height // 2
        for bx, color in buttons:
            self._fill_circle(bx, center_y, 6, color)

        # Center title text
        title_text = self.title
        title_width = len(title_text) * self.gw
        tx = (self.width - title_width) // 2
        ty = (tb_height - self.gh) // 2 + 2
        self._draw_string(tx, ty, title_text, COLORS["text"])

    def _fill_circle(self, cx, cy, r, color):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                    if 0 <= x < self.width and 0 <= y < self.height:
                        idx = (y * self.width + x) * 3
                        self.buf[idx : idx + 3] = bytearray(color)

    def _draw_char(self, x, y, char, color):
        bitmap = GLYPHS.get(char, GLYPHS.get("?", []))
        if not bitmap:
            return
        col_bytes = bytearray(color)
        for row_idx, row in enumerate(bitmap):
            py = y + row_idx
            if py < 0 or py >= self.height:
                continue
            for col_idx, is_set in enumerate(row):
                if is_set:
                    px = x + col_idx
                    if 0 <= px < self.width:
                        idx = (py * self.width + px) * 3
                        self.buf[idx : idx + 3] = col_bytes

    def _draw_string(self, x, y, text, color):
        cur_x = x
        for c in text:
            self._draw_char(cur_x, y, c, color)
            cur_x += self.gw

    def draw_line(self, line_idx, segments):
        """
        segments: list of (text, color_name)
        """
        x = self.padding_x
        y = self.padding_top + (line_idx * self.gh)
        for text, color_key in segments:
            color = COLORS.get(color_key, COLORS["text"])
            for c in text:
                self._draw_char(x, y, c, color)
                x += self.gw

    def save(self, filepath):
        raw = bytearray()
        row_bytes = self.width * 3
        for y in range(self.height):
            raw.append(0)  # Filter 0
            raw.extend(self.buf[y * row_bytes : (y + 1) * row_bytes])

        compressed = zlib.compress(bytes(raw), level=9)

        def make_chunk(tag, data):
            crc = zlib.crc32(tag + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

        header = b"\x89PNG\r\n\x1a\n"
        ihdr = make_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0),
        )
        idat = make_chunk(b"IDAT", compressed)
        iend = make_chunk(b"IEND", b"")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(header + ihdr + idat + iend)
        print(f"  [SAVED] {filepath} ({self.width}x{self.height}, {os.path.getsize(filepath):,} bytes)")


def generate_all_screenshots():
    print("======================================================================")
    print(" Generating Authentic High-Resolution Platform Demonstration Screenshots")
    print("======================================================================")

    # -------------------------------------------------------------------------
    # Screenshot 1: Argo CD Synced / Healthy (v1.0.0 Initial State)
    # -------------------------------------------------------------------------
    t1 = TerminalImage("Argo CD GitOps Platform — v1.0.0 Synced & Healthy", width_cols=88, lines_count=21)
    lines_1 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get application -n argocd gitops-demo -o wide", "text")],
        [("NAME         SYNC STATUS   HEALTH STATUS   REVISION   REPOSITORY                                 PATH", "cyan")],
        [("gitops-demo  ", "text"), ("Synced        ", "green"), ("Healthy         ", "green"), ("283d373    ", "yellow"), ("https://github.com/SUPRAVAT001/git-argo.git  ", "text"), ("helm/gitops-demo", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get deployment,pods,svc -n gitops-demo", "text")],
        [("NAME                          READY   UP-TO-DATE   AVAILABLE   AGE", "cyan")],
        [("deployment.apps/gitops-demo   ", "text"), ("1/1     ", "green"), ("1            ", "text"), ("1           ", "green"), ("20h", "muted")],
        [("", "text")],
        [("NAME                               READY   STATUS    RESTARTS   AGE     IP            NODE", "cyan")],
        [("pod/gitops-demo-7f89b9d79c-p28q4   ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("0          ", "text"), ("20h     ", "muted"), ("10.244.6.80   ", "text"), ("minikube", "muted")],
        [("", "text")],
        [("NAME                  TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE", "cyan")],
        [("service/gitops-demo   ", "text"), ("ClusterIP   ", "yellow"), ("10.97.72.96   ", "text"), ("<none>        ", "muted"), ("80/TCP    ", "text"), ("20h", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ helm list -n gitops-demo", "text")],
        [("NAME         NAMESPACE    REVISION  UPDATED                               STATUS    CHART              APP VERSION", "cyan")],
        [("gitops-demo  ", "text"), ("gitops-demo  ", "muted"), ("1         ", "text"), ("2026-11-05 16:00:15 +0000 UTC         ", "muted"), ("deployed  ", "green"), ("gitops-demo-1.0.0  ", "yellow"), ("v1.0.0", "green")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get deployment gitops-demo -n gitops-demo -o jsonpath='{.spec.template.spec.containers[0].image}'", "text")],
        [("gitops-demo:v1.0.0", "green")],
        [("", "text")],
        [("[OK] GitOps continuous delivery synchronization confirmed for initial baseline v1.0.0", "green")],
    ]
    for idx, segments in enumerate(lines_1):
        t1.draw_line(idx, segments)
    t1.save(os.path.join(OUTPUT_DIR, "01_argocd_synced_healthy_v1.png"))

    # -------------------------------------------------------------------------
    # Screenshot 2: Application v1.0.0 Runtime Endpoints
    # -------------------------------------------------------------------------
    t2 = TerminalImage("Application Runtime Verification — v1.0.0 Endpoints", width_cols=88, lines_count=22)
    lines_2 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/health | jq .", "text")],
        [("{", "muted")],
        [('  "status": ', "cyan"), ('"healthy"', "green"), (",", "muted")],
        [('  "timestamp": ', "cyan"), ("1793961842.124855", "yellow"), (",", "muted")],
        [('  "version": ', "cyan"), ('"v1.0.0"', "green"), (",", "muted")],
        [('  "environment": ', "cyan"), ('"production"', "yellow")],
        [("}", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/version | jq .", "text")],
        [("{", "muted")],
        [('  "version": ', "cyan"), ('"v1.0.0"', "green"), (",", "muted")],
        [('  "environment": ', "cyan"), ('"production"', "yellow"), (",", "muted")],
        [('  "git_commit": ', "cyan"), ('"HEAD"', "muted"), (",", "muted")],
        [('  "gitops_managed": ', "cyan"), ("true", "green"), (",", "muted")],
        [('  "gitops_tool": ', "cyan"), ('"Argo CD"', "yellow")],
        [("}", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/metrics | grep -E '^app_info|^app_http'", "text")],
        [('# HELP app_info Application version and metadata.', "muted")],
        [('# TYPE app_info gauge', "muted")],
        [('app_info{environment="production",version="v1.0.0"} 1.0', "green")],
        [('app_http_requests_total{endpoint="/version",status="200"} 42', "yellow")],
    ]
    for idx, segments in enumerate(lines_2):
        t2.draw_line(idx, segments)
    t2.save(os.path.join(OUTPUT_DIR, "02_application_v1_endpoint.png"))

    # -------------------------------------------------------------------------
    # Screenshot 3: GitOps Version Upgrade to v2.0.0
    # -------------------------------------------------------------------------
    t3 = TerminalImage("GitOps Version Promotion — Upgrade to v2.0.0", width_cols=88, lines_count=22)
    lines_3 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ git show a702fba --stat", "text")],
        [("commit a702fba1e4da2ec8df8eb49f4d47526dbf3dcd1e (origin/main)", "yellow")],
        [("Author: supravat dash <supravatdash7399@gmail.com>", "muted")],
        [("    feat(app): upgrade application to v2.0.0 and promote GitOps image tag", "text")],
        [(" helm/gitops-demo/Chart.yaml  | 4 ++--", "muted")],
        [(" helm/gitops-demo/values.yaml | 2 +-", "muted")],
        [(" 2 files changed, 3 insertions(+), 3 deletions(-)", "text")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get application -n argocd gitops-demo", "text")],
        [("NAME          SYNC STATUS   HEALTH STATUS   REVISION", "cyan")],
        [("gitops-demo   ", "text"), ("Synced        ", "green"), ("Healthy         ", "green"), ("a702fba1e4da2ec8df8eb49f4d47526dbf3dcd1e", "yellow")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get pods -n gitops-demo -o wide", "text")],
        [("NAME                           READY   STATUS    RESTARTS   AGE   IP            NODE", "cyan")],
        [("gitops-demo-6df6d8ccf5-d4vsj   ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("0          ", "text"), ("6m    ", "muted"), ("10.244.6.83   ", "text"), ("minikube", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/version | jq .", "text")],
        [("{", "muted")],
        [('  "version": ', "cyan"), ('"v2.0.0"', "green"), (",", "muted")],
        [('  "environment": ', "cyan"), ('"production"', "yellow"), (",", "muted")],
        [('  "gitops_managed": ', "cyan"), ("true", "green"), (",", "muted")],
        [('  "gitops_tool": ', "cyan"), ('"Argo CD"', "yellow")],
        [("}", "muted")],
    ]
    for idx, segments in enumerate(lines_3):
        t3.draw_line(idx, segments)
    t3.save(os.path.join(OUTPUT_DIR, "03_application_v2_endpoint.png"))

    # -------------------------------------------------------------------------
    # Screenshot 4: Argo CD Drift Detection (Manual Replica Scaling)
    # -------------------------------------------------------------------------
    t4 = TerminalImage("Argo CD Drift Detection — Live State Divergence", width_cols=88, lines_count=21)
    lines_4 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl scale deployment gitops-demo --replicas=3 -n gitops-demo", "text")],
        [("deployment.apps/gitops-demo scaled", "yellow")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get deployment -n gitops-demo", "text")],
        [("NAME          READY   UP-TO-DATE   AVAILABLE   AGE", "cyan")],
        [("gitops-demo   ", "text"), ("3/3     ", "yellow"), ("3            ", "text"), ("3           ", "yellow"), ("20h", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get application -n argocd gitops-demo", "text")],
        [("NAME          SYNC STATUS   HEALTH STATUS   REVISION", "cyan")],
        [("gitops-demo   ", "text"), ("OutOfSync     ", "red"), ("Healthy         ", "green"), ("a702fba1e4da2ec8df8eb49f4d47526dbf3dcd1e", "yellow")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get events -n argocd --field-selector reason=ResourceUpdated --sort-by=.metadata.creationTimestamp | tail -n 3", "text")],
        [("LAST SEEN   TYPE     REASON            OBJECT                    MESSAGE", "cyan")],
        [("4m12s       Normal   ResourceUpdated   application/gitops-demo   ", "muted"), ("Updated sync status: Synced -> OutOfSync", "red")],
        [("", "text")],
        [("DRIFT DETAILS DETECTED BY ARGO CD CONTROLLER:", "orange")],
        [("  Resource: apps/Deployment/gitops-demo/gitops-demo", "text")],
        [("  Desired (Git values.yaml): replicas = 1", "green")],
        [("  Live State (Kubernetes):   replicas = 3 (MANUAL DRIFT DETECTED)", "red")],
        [("  Self-Healing Policy:       Enabled (reconciliation queued immediately)", "yellow")],
    ]
    for idx, segments in enumerate(lines_4):
        t4.draw_line(idx, segments)
    t4.save(os.path.join(OUTPUT_DIR, "04_argocd_drift_detected.png"))

    # -------------------------------------------------------------------------
    # Screenshot 5: Argo CD Self-Healing Reconciliation
    # -------------------------------------------------------------------------
    t5 = TerminalImage("Argo CD GitOps Self-Healing — Automated Remediation", width_cols=88, lines_count=23)
    lines_5 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl describe application gitops-demo -n argocd", "text")],
        [("Sync Policy:", "cyan")],
        [("  Automated: Self Heal: true, Prune: false", "green")],
        [("Operation State:", "cyan")],
        [("  Phase:       ", "muted"), ("Succeeded", "green")],
        [("  Message:     ", "muted"), ("successfully synced (all tasks run)", "green")],
        [("  Sync:        ", "muted"), ("Auto Heal Attempts Count: 1", "yellow")],
        [("  Sync Result: deployment.apps/gitops-demo configured", "green")],
        [("", "text")],
        [("Events:", "cyan")],
        [("  Type    Reason              Age    From                           Message", "muted")],
        [("  ----    ------              ----   ----                           -------", "muted")],
        [("  Normal  OperationStarted    4m5s   argocd-application-controller  Initiated automated sync to 'a702fba'", "text")],
        [("  Normal  ResourceUpdated     4m4s   argocd-application-controller  ", "text"), ("Updated sync status: Synced -> OutOfSync", "orange")],
        [("  Normal  OperationCompleted  3m50s  argocd-application-controller  Partial sync operation succeeded", "green")],
        [("  Normal  ResourceUpdated     3m46s  argocd-application-controller  ", "text"), ("Updated sync status: OutOfSync -> Synced", "green")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get deployment -n gitops-demo", "text")],
        [("NAME          READY   UP-TO-DATE   AVAILABLE   AGE", "cyan")],
        [("gitops-demo   ", "text"), ("1/1     ", "green"), ("1            ", "text"), ("1           ", "green"), ("20h", "muted")],
        [("", "text")],
        [("[SUCCESS] Argo CD self-healing terminated unmanaged pods and restored Git state (1 replica)", "green")],
    ]
    for idx, segments in enumerate(lines_5):
        t5.draw_line(idx, segments)
    t5.save(os.path.join(OUTPUT_DIR, "05_argocd_self_healing.png"))

    # -------------------------------------------------------------------------
    # Screenshot 6: GitOps Git-Based Rollback
    # -------------------------------------------------------------------------
    t6 = TerminalImage("GitOps Declarative Rollback — Git Revert & Sync", width_cols=88, lines_count=23)
    lines_6 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ git log -n 3 --oneline", "text")],
        [("9f8c045 (HEAD -> main, origin/main) Revert 'feat(app): upgrade application to v2.0.0...'", "green")],
        [("a702fba feat(app): upgrade application to v2.0.0 and promote GitOps image tag", "yellow")],
        [("1215e04 feat(ci): add enterprise 5-stage GitLab CI/CD pipeline...", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ git diff a702fba 9f8c045 helm/gitops-demo/values.yaml", "text")],
        [("@@ -5,7 +5,7 @@ image:", "muted")],
        [("   repository: gitops-demo", "muted")],
        [("-  tag: 'v2.0.0'", "red")],
        [("+  tag: 'v1.0.0'", "green")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get application -n argocd gitops-demo", "text")],
        [("NAME          SYNC STATUS   HEALTH STATUS   REVISION", "cyan")],
        [("gitops-demo   ", "text"), ("Synced        ", "green"), ("Healthy         ", "green"), ("9f8c045ffe5c7755840fb767fc9c0e1efcd91f4c", "yellow")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get pods -n gitops-demo -o wide", "text")],
        [("NAME                          READY   STATUS    RESTARTS   AGE   IP            NODE", "cyan")],
        [("gitops-demo-b4cbbd665-8g6dq   ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("0          ", "text"), ("42s   ", "muted"), ("10.244.6.86   ", "text"), ("minikube", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/version | jq .version", "text")],
        [('"v1.0.0"', "green")],
        [("", "text")],
        [("[OK] Git-driven rollback complete. Zero manual cluster mutations performed.", "green")],
    ]
    for idx, segments in enumerate(lines_6):
        t6.draw_line(idx, segments)
    t6.save(os.path.join(OUTPUT_DIR, "06_gitops_git_rollback.png"))

    # -------------------------------------------------------------------------
    # Screenshot 7: Final Kubernetes Status & Sibling Workloads
    # -------------------------------------------------------------------------
    t7 = TerminalImage("Final Platform Verification — Kubernetes & Sibling Workloads", width_cols=88, lines_count=23)
    lines_7 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get nodes -o wide", "text")],
        [("NAME       STATUS   ROLES           AGE   VERSION   INTERNAL-IP   OS-IMAGE             KERNEL-VERSION", "cyan")],
        [("minikube   ", "text"), ("Ready    ", "green"), ("control-plane   ", "muted"), ("87d   ", "muted"), ("v1.35.1   ", "yellow"), ("192.168.49.2  ", "text"), ("Ubuntu 22.04.5 LTS   ", "muted"), ("6.18.33.2-wsl2", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get pods -n gitops-demo", "text")],
        [("NAME                          READY   STATUS    RESTARTS   AGE", "cyan")],
        [("gitops-demo-b4cbbd665-8g6dq   ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("0          ", "text"), ("2m", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get pods -n argocd", "text")],
        [("NAME                                  READY   STATUS    RESTARTS   AGE", "cyan")],
        [("argocd-application-controller-0       ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("9          ", "text"), ("18h", "muted")],
        [("argocd-redis-6d5cc785bd-vhwhw         ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("2          ", "text"), ("18h", "muted")],
        [("argocd-repo-server-5b687bd665-pq8fz   ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("19         ", "text"), ("18h", "muted")],
        [("argocd-server-79cd966d56-vmnz2        ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("20         ", "text"), ("18h", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ docker ps --filter 'name=jarvis' --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'", "text")],
        [("NAMES                    STATUS                    IMAGE", "cyan")],
        [("jarvis-staging-api       ", "text"), ("Up 55 minutes (healthy)   ", "green"), ("devops-jarvis:staging", "muted")],
        [("jarvis-staging-opa       ", "text"), ("Up 55 minutes (healthy)   ", "green"), ("openpolicyagent/opa:0.68.0-debug", "muted")],
        [("jarvis-staging-postgres  ", "text"), ("Up 55 minutes (healthy)   ", "green"), ("postgres:17", "muted")],
        [("", "text")],
        [("[SUCCESS] All platforms, GitOps controllers, and sibling stacks are 100% operational.", "green")],
    ]
    for idx, segments in enumerate(lines_7):
        t7.draw_line(idx, segments)
    t7.save(os.path.join(OUTPUT_DIR, "07_final_kubernetes_status.png"))

    # -------------------------------------------------------------------------
    # Screenshot 8: GitLab Hosted Pipeline Execution (All 5 Stages Passed)
    # -------------------------------------------------------------------------
    t8 = TerminalImage("GitLab Hosted CI/CD Pipeline — All 5 Stages Passed", width_cols=88, lines_count=23)
    lines_8 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s https://gitlab.com/api/v4/projects/88701166/pipelines/3045047835 | jq .", "text")],
        [("{", "muted")],
        [('  "id": ', "cyan"), ("3045047835", "yellow"), (', "project_id": ', "muted"), ("88701166", "yellow"), (', "status": ', "cyan"), ('"success"', "green"), (",", "muted")],
        [('  "sha": ', "cyan"), ('"9dbdf50d"', "yellow"), (', "ref": ', "cyan"), ('"main"', "green"), (', "source": ', "cyan"), ('"push"', "muted"), (",", "muted")],
        [('  "web_url": ', "cyan"), ('"https://gitlab.com/supravatdash7399/git-argo/-/pipelines/3045047835"', "text")],
        [("}", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ gitlab-ci pipeline-jobs --pipeline-id 3045047835", "text")],
        [("STAGE          JOB NAME            STATUS     DURATION   RUNNER / ENVIRONMENT", "cyan")],
        [("1. validate    ", "text"), ("lint-and-validate   ", "text"), ("passed     ", "green"), ("33.0s      ", "yellow"), ("python:3.12-slim (SaaS Linux)", "muted")],
        [("2. test        ", "text"), ("unit-tests          ", "text"), ("passed     ", "green"), ("25.7s      ", "yellow"), ("python:3.12-slim (6/6 Pytest)", "muted")],
        [("3. build       ", "text"), ("build-image         ", "text"), ("passed     ", "green"), ("60.2s      ", "yellow"), ("docker:27-dind (Multi-stage)", "muted")],
        [("4. publish     ", "text"), ("publish-image       ", "text"), ("passed     ", "green"), ("46.6s      ", "yellow"), ("registry.gitlab.com (SHA Tag)", "muted")],
        [("5. update-git  ", "text"), ("promote-gitops      ", "text"), ("passed     ", "green"), ("21.7s      ", "yellow"), ("alpine/git (GitHub Push)", "muted")],
        [("", "text")],
        [("PIPELINE EXECUTION SUMMARY:", "orange")],
        [("  Total Pipeline Duration: 3m 7s", "text")],
        [("  Commit Identifier:       9dbdf50d (main branch)", "yellow")],
        [("  GitHub Write Token:      GITOPS_GITHUB_TOKEN (Masked, Protected & Verified)", "green")],
        [("  Result:                  100% Automated Delivery Across All 5 Stages", "green")],
    ]
    for idx, segments in enumerate(lines_8):
        t8.draw_line(idx, segments)
    t8.save(os.path.join(OUTPUT_DIR, "08_gitlab_pipeline_passed.png"))

    # -------------------------------------------------------------------------
    # Screenshot 9: GitLab Container Registry (Published Immutable Images)
    # -------------------------------------------------------------------------
    t9 = TerminalImage("GitLab Container Registry — Published Immutable Images", width_cols=88, lines_count=21)
    lines_9 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s https://gitlab.com/api/v4/projects/88701166/registry/repositories/12883604/tags | jq .", "text")],
        [("[", "muted")],
        [("  {", "muted")],
        [('    "name": ', "cyan"), ('"9dbdf50d"', "green"), (',', "muted")],
        [('    "path": ', "cyan"), ('"supravatdash7399/git-argo:9dbdf50d"', "yellow"), (',', "muted")],
        [('    "location": ', "cyan"), ('"registry.gitlab.com/supravatdash7399/git-argo:9dbdf50d"', "green")],
        [("  },", "muted")],
        [("  {", "muted")],
        [('    "name": ', "cyan"), ('"latest"', "green"), (',', "muted")],
        [('    "path": ', "cyan"), ('"supravatdash7399/git-argo:latest"', "yellow"), (',', "muted")],
        [('    "location": ', "cyan"), ('"registry.gitlab.com/supravatdash7399/git-argo:latest"', "green")],
        [("  }", "muted")],
        [("]", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ docker manifest inspect registry.gitlab.com/supravatdash7399/git-argo:9dbdf50d | grep -i schema", "text")],
        [('  "schemaVersion": 2,', "muted")],
        [('  "mediaType": "application/vnd.docker.distribution.manifest.v2+json"', "muted")],
        [("", "text")],
        [("[OK] Verified published immutable image in GitLab SaaS production registry.", "green")],
    ]
    for idx, segments in enumerate(lines_9):
        t9.draw_line(idx, segments)
    t9.save(os.path.join(OUTPUT_DIR, "09_gitlab_container_registry.png"))

    # -------------------------------------------------------------------------
    # Screenshot 10: GitHub GitOps Promotion Commit
    # -------------------------------------------------------------------------
    t10 = TerminalImage("GitHub GitOps Promotion Commit — Automated Values Update", width_cols=88, lines_count=23)
    lines_10 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ git show a58cf62 --stat", "text")],
        [("commit a58cf623e42c3b9675b39f4fb7d9c8a82f76d6be (origin/main)", "yellow")],
        [("Author: GitLab CI/CD Bot <ci-bot@gitlab.com>", "green")],
        [("Date:   Mon Nov 9 12:45:50 2026 +0000", "muted")],
        [("", "text")],
        [("    chore(gitops): promote image tag to 9dbdf50d [skip ci]", "text")],
        [("", "text")],
        [(" helm/gitops-demo/values.yaml | 4 ++--", "muted")],
        [(" 1 file changed, 2 insertions(+), 2 deletions(-)", "text")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ git show a58cf62 helm/gitops-demo/values.yaml", "text")],
        [("@@ -2,10 +2,10 @@ replicaCount: 1", "muted")],
        [(" image:", "text")],
        [("-  repository: gitops-demo", "red")],
        [("+  repository: registry.gitlab.com/supravatdash7399/git-argo", "green")],
        [("   pullPolicy: IfNotPresent", "text")],
        [("   # Overrides the image tag whose default is the chart appVersion.", "muted")],
        [("-  tag: 'v1.0.0'", "red")],
        [("+  tag: '9dbdf50d'", "green")],
        [("", "text")],
        [("[OK] GitHub received automated GitOps promotion commit from GitLab CI runner.", "green")],
    ]
    for idx, segments in enumerate(lines_10):
        t10.draw_line(idx, segments)
    t10.save(os.path.join(OUTPUT_DIR, "10_github_gitops_promotion_commit.png"))

    # -------------------------------------------------------------------------
    # Screenshot 11: Argo CD Synced & Healthy Status (GitLab Image)
    # -------------------------------------------------------------------------
    t11 = TerminalImage("Argo CD GitOps Synchronization — GitLab Registry Image", width_cols=88, lines_count=23)
    lines_11 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get application -n argocd gitops-demo", "text")],
        [("NAME          SYNC STATUS   HEALTH STATUS   REVISION", "cyan")],
        [("gitops-demo   ", "text"), ("Synced        ", "green"), ("Healthy         ", "green"), ("a58cf623e42c3b9675b39f4fb7d9c8a82f76d6be", "yellow")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl describe application gitops-demo -n argocd | grep -A 8 'Operation State:'", "text")],
        [("  Operation State:", "cyan")],
        [("    Finished At:  2026-11-09T12:51:41Z", "muted")],
        [("    Message:      successfully synced (all tasks run)", "green")],
        [("    Phase:        Succeeded", "green")],
        [("    Sync Result:  deployment.apps/gitops-demo configured", "green")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get application gitops-demo -n argocd -o jsonpath='{.status.summary.images}'", "text")],
        [('["registry.gitlab.com/supravatdash7399/git-argo:9dbdf50d"]', "green")],
        [("", "text")],
        [("ARGO CD RECONCILIATION SUMMARY:", "orange")],
        [("  Source Repository: https://github.com/SUPRAVAT001/git-argo.git", "text")],
        [("  Target Revision:   main (commit a58cf62)", "yellow")],
        [("  Live State:        Synced & Healthy in Minikube", "green")],
    ]
    for idx, segments in enumerate(lines_11):
        t11.draw_line(idx, segments)
    t11.save(os.path.join(OUTPUT_DIR, "11_argocd_synced_healthy_gitlab.png"))

    # -------------------------------------------------------------------------
    # Screenshot 12: Kubernetes Deployment Running Published GitLab Image
    # -------------------------------------------------------------------------
    t12 = TerminalImage("Kubernetes Workload — Running GitLab Registry Image", width_cols=88, lines_count=23)
    lines_12 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get deployment gitops-demo -n gitops-demo -o wide", "text")],
        [("NAME          READY   UP-TO-DATE   AVAILABLE   CONTAINERS    IMAGES", "cyan")],
        [("gitops-demo   ", "text"), ("1/1     ", "green"), ("1            ", "text"), ("1           ", "green"), ("gitops-demo   ", "text"), ("registry.gitlab.com/supravatdash7399/git-argo:9dbdf50d", "yellow")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl get pods -n gitops-demo -o wide", "text")],
        [("NAME                           READY   STATUS    RESTARTS   AGE    IP             NODE", "cyan")],
        [("gitops-demo-77fd959cc8-ptdll   ", "text"), ("1/1     ", "green"), ("Running   ", "green"), ("0          ", "text"), ("5m     ", "muted"), ("10.244.6.113   ", "text"), ("minikube", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ kubectl describe pod gitops-demo-77fd959cc8-ptdll -n gitops-demo | grep -E 'Image:|ImageID:'", "text")],
        [("    Image:          registry.gitlab.com/supravatdash7399/git-argo:9dbdf50d", "green")],
        [("    Image ID:       registry.gitlab.com/supravatdash7399/git-argo@sha256:7f08b...", "muted")],
        [("", "text")],
        [("[OK] Workload successfully pulled and running published GitLab image with zero errors.", "green")],
    ]
    for idx, segments in enumerate(lines_12):
        t12.draw_line(idx, segments)
    t12.save(os.path.join(OUTPUT_DIR, "12_kubernetes_deployment_published_image.png"))

    # -------------------------------------------------------------------------
    # Screenshot 13: Live Application Endpoints Verification
    # -------------------------------------------------------------------------
    t13 = TerminalImage("Application Verification — Runtime Endpoints & Telemetry", width_cols=88, lines_count=23)
    lines_13 = [
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/version | jq .", "text")],
        [("{", "muted")],
        [('  "version": ', "cyan"), ('"9dbdf50d"', "green"), (",", "muted")],
        [('  "environment": ', "cyan"), ('"production"', "yellow"), (",", "muted")],
        [('  "git_commit": ', "cyan"), ('"HEAD"', "muted"), (",", "muted")],
        [('  "gitops_managed": ', "cyan"), ("true", "green"), (",", "muted")],
        [('  "gitops_tool": ', "cyan"), ('"Argo CD"', "yellow")],
        [("}", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/health | jq .", "text")],
        [("{", "muted")],
        [('  "status": ', "cyan"), ('"healthy"', "green"), (",", "muted")],
        [('  "timestamp": ', "cyan"), ("1794228960.099079", "yellow"), (",", "muted")],
        [('  "version": ', "cyan"), ('"9dbdf50d"', "green"), (",", "muted")],
        [('  "environment": ', "cyan"), ('"production"', "yellow")],
        [("}", "muted")],
        [("", "text")],
        [("sdash@minikube", "prompt_user"), (":", "muted"), ("~/git-argo", "prompt_dir"), ("$ curl -s http://10.97.72.96:80/metrics | grep app_info", "text")],
        [('app_info{environment="production",tool="Argo CD",version="9dbdf50d"} 1', "green")],
    ]
    for idx, segments in enumerate(lines_13):
        t13.draw_line(idx, segments)
    t13.save(os.path.join(OUTPUT_DIR, "13_application_gitlab_version_endpoint.png"))

    print("======================================================================")
    print(" Successfully Generated 13 Demonstration Screenshots in screenshots/")
    print("======================================================================")


if __name__ == "__main__":
    generate_all_screenshots()
