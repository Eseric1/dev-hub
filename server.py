#!/usr/bin/env python3
"""
Field Intel Server
Launched by launch.py — not intended for direct use.

Persists observations to disk at observations/entries.json
Security mirrors file explorer: 127.0.0.1 only, token auth,
host validation, rate limiting.
"""

import os, sys, json, secrets, time, urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "observations"
DATA_DIR.mkdir(exist_ok=True)
ENTRIES_FILE = DATA_DIR / "entries.json"

PORT  = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
TOKEN = sys.argv[2]      if len(sys.argv) > 2 else secrets.token_urlsafe(32)

ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

# ── Rate limiter ──────────────────────────────────────────────────────────────
_bad_requests = defaultdict(int)
_locked_until = defaultdict(float)
MAX_BAD       = 20
LOCKOUT       = 300

def is_rate_limited(ip):
    return time.time() < _locked_until[ip]

def record_bad(ip):
    _bad_requests[ip] += 1
    if _bad_requests[ip] >= MAX_BAD:
        _locked_until[ip] = time.time() + LOCKOUT
        _bad_requests[ip] = 0

# ── Data helpers ──────────────────────────────────────────────────────────────
def load_entries():
    try:
        if ENTRIES_FILE.exists():
            return json.loads(ENTRIES_FILE.read_text())
    except Exception:
        pass
    return []

def save_entries(entries):
    ENTRIES_FILE.write_text(json.dumps(entries, indent=2))

# ── Handler ───────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silent

    def _check_security(self, require_token=True):
        ip   = self.client_address[0]
        host = self.headers.get("Host", "")

        if is_rate_limited(ip):
            self._deny(429, "Too many bad requests.")
            return False

        if host not in ALLOWED_HOSTS:
            record_bad(ip)
            self._deny(403, "Invalid host.")
            return False

        if not require_token:
            return True

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        tok    = params.get("_t", [""])[0]

        if not secrets.compare_digest(tok, TOKEN):
            record_bad(ip)
            self._deny(403, "Forbidden.")
            return False

        return True

    def _deny(self, status, msg):
        body = json.dumps({"error": msg}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, p):
        try:
            data = p.read_bytes()
        except Exception:
            self._deny(404, "Not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        # Bootstrap — no token needed
        if path == "/bootstrap":
            host = self.headers.get("Host", "")
            if host not in ALLOWED_HOSTS:
                self._deny(403, "Invalid host.")
                return
            self.send_json({"token": TOKEN})
            return

        # Frontend
        if path in ("/", "/index.html"):
            host = self.headers.get("Host", "")
            if host not in ALLOWED_HOSTS:
                self._deny(403, "Invalid host.")
                return
            html = BASE_DIR / "index.html"
            if html.exists():
                self.send_file(html)
            else:
                self._deny(404, "index.html not found.")
            return

        if not self._check_security():
            return

        # Get all entries
        if path == "/api/entries":
            self.send_json({"entries": load_entries()})
            return

        # Get stats summary
        if path == "/api/stats":
            entries = load_entries()
            cats    = defaultdict(int)
            refs    = defaultdict(int)
            for e in entries:
                cats[e.get("category","other")] += 1
                for r in (e.get("references") or []):
                    if r: refs[r] += 1
            self.send_json({
                "total":      len(entries),
                "categories": dict(cats),
                "top_refs":   sorted(refs.items(), key=lambda x: -x[1])[:10]
            })
            return

        self._deny(404, "Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        if not self._check_security():
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body        = self.rfile.read(content_len)

        try:
            data = json.loads(body)
        except Exception:
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        # Save a new entry
        if path == "/api/entries":
            required = ["id", "tool", "category", "observation"]
            if not all(k in data for k in required):
                self.send_json({"error": "Missing required fields"}, 400)
                return

            entries = load_entries()

            # Prevent duplicates by ID
            if any(e.get("id") == data["id"] for e in entries):
                self.send_json({"ok": True, "note": "duplicate"})
                return

            entries.insert(0, data)
            save_entries(entries)
            self.send_json({"ok": True, "total": len(entries)})
            return

        self._deny(404, "Not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        if not self._check_security():
            return

        # Delete entry by ID: DELETE /api/entries/<id>
        if path.startswith("/api/entries/"):
            entry_id = path.split("/")[-1]
            try:
                entry_id = int(entry_id)
            except ValueError:
                self.send_json({"error": "Invalid ID"}, 400)
                return

            entries = load_entries()
            before  = len(entries)
            entries = [e for e in entries if e.get("id") != entry_id]

            if len(entries) == before:
                self.send_json({"error": "Entry not found"}, 404)
                return

            save_entries(entries)
            self.send_json({"ok": True, "total": len(entries)})
            return

        self._deny(404, "Not found")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"READY:{PORT}:{TOKEN}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass