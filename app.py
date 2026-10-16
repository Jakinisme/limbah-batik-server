"""
Entry Hugging Face Space: halaman status di port 7860 + listener Firebase 24 jam.

Jalankan: python app.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import HOST, PORT
from main import STATUS, start_backend

PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta http-equiv="refresh" content="15"/>
  <title>NIPRO EC backend</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ font: 16px/1.45 ui-sans-serif, system-ui, sans-serif; margin: 0;
           background: #111; color: #eee; }}
    main {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.25rem; font-weight: 650; }}
    .ok {{ color: #8fd18f; }} .bad {{ color: #f0a0a0; }} .warn {{ color: #e6c07b; }}
    pre {{ background: #1c1c1c; padding: 1rem; overflow: auto; font-size: 0.85rem; }}
    p.note {{ color: #aaa; font-size: 0.9rem; }}
  </style>
</head>
<body>
<main>
  <h1>NIPRO 2026 — backend elektrokoagulasi</h1>
  <p>Listener: <strong class="{cls}">{listener}</strong></p>
  <p>Model: {version} — label <strong>{label}</strong></p>
  <p>Firebase: {fb} · event terakhir: {event}</p>
  {warn}
  <h2>Rekomendasi terakhir</h2>
  <pre>{rec}</pre>
  <p class="note">Halaman ini hanya status. Perintah EC ditulis ke
  <code>/recommendations/ec/latest</code>. Refresh otomatis 15 detik.
  Endpoint JSON: <a href="/health">/health</a></p>
</main>
</body>
</html>
"""


def _public_status():
    return {
        "ok": STATUS.get("listener") == "running" and STATUS.get("model_loaded"),
        "listener": STATUS.get("listener"),
        "firebase": STATUS.get("firebase"),
        "model_loaded": STATUS.get("model_loaded"),
        "model_version": STATUS.get("model_version"),
        "data_label": STATUS.get("data_label"),
        "last_rec": STATUS.get("last_rec"),
        "last_error": STATUS.get("last_error"),
        "last_event_at": STATUS.get("last_event_at"),
        "started_at": STATUS.get("started_at"),
        "now": datetime.now(timezone.utc).isoformat(),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        st = _public_status()
        if path in ("/health", "/status", "/api/status"):
            self._send(200 if st["ok"] else 503, json.dumps(st, indent=2), "application/json; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            listener = st["listener"] or "unknown"
            cls = "ok" if listener == "running" else "bad"
            warn = ""
            if st.get("data_label") == "ASLI":
                warn = '<p class="warn">Model ASLI.</p>'
            if st.get("last_error"):
                warn += f'<p class="bad">Error: {st["last_error"]}</p>'
            rec = json.dumps(st.get("last_rec"), indent=2, ensure_ascii=False) if st.get("last_rec") else "(belum ada)"
            html = PAGE.format(
                cls=cls,
                listener=listener,
                version=st.get("model_version") or "-",
                label=st.get("data_label") or "-",
                fb="terhubung" if st.get("firebase") else "tidak",
                event=st.get("last_event_at") or "-",
                warn=warn,
                rec=rec,
            )
            self._send(200, html, "text/html; charset=utf-8")
            return
        self._send(404, "not found", "text/plain; charset=utf-8")


def main():
    start_backend()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[http] status di http://{HOST}:{PORT}/  (health: /health)")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
