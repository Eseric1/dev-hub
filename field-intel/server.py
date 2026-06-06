#!/usr/bin/env python3
import os, sys, json, secrets, time, urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

BASE_DIR     = Path(__file__).parent.resolve()
DATA_DIR     = BASE_DIR / "observations"
DATA_DIR.mkdir(exist_ok=True)
ENTRIES_FILE = DATA_DIR / "entries.json"

PORT  = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
TOKEN = sys.argv[2]      if len(sys.argv) > 2 else secrets.token_urlsafe(32)

_bad_requests = defaultdict(int)
_locked_until = defaultdict(float)

def is_rate_limited(ip):
    return time.time() < _locked_until[ip]

def record_bad(ip):
    _bad_requests[ip] += 1
    if _bad_requests[ip] >= 20:
        _locked_until[ip] = time.time() + 300
        _bad_requests[ip] = 0

def load_entries():
    try:
        if ENTRIES_FILE.exists():
            return json.loads(ENTRIES_FILE.read_text())
    except Exception:
        pass
    return []

def save_entries(entries):
    ENTRIES_FILE.write_text(json.dumps(entries, indent=2))

def is_local_host(host):
    return host.startswith("127.0.0.1:") or host.startswith("localhost:")

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

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
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, p):
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

    def check_token(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        tok    = params.get("_t", [""])[0]
        return secrets.compare_digest(tok, TOKEN)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        ip     = self.client_address[0]
        host   = self.headers.get("Host", "")
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        if is_rate_limited(ip):
            self._deny(429, "Rate limited")
            return

        if not is_local_host(host):
            record_bad(ip)
            self._deny(403, "Invalid host")
            return

        if path == "/bootstrap":
            self.send_json({"token": TOKEN})
            return

        if path in ("/", "/index.html"):
            html = BASE_DIR / "index.html"
            if html.exists():
                self.send_html(html)
            else:
                self._deny(404, "index.html not found")
            return

        if not self.check_token():
            record_bad(ip)
            self._deny(403, "Forbidden")
            return

        if path == "/api/entries":
            self.send_json({"entries": load_entries()})
            return

        if path == "/api/stats":
            entries = load_entries()
            cats = defaultdict(int)
            refs = defaultdict(int)
            for e in entries:
                cats[e.get("category", "other")] += 1
                for r in (e.get("references") or []):
                    if r:
                        refs[r] += 1
            self.send_json({
                "total":      len(entries),
                "categories": dict(cats),
                "top_refs":   sorted(refs.items(), key=lambda x: -x[1])[:10]
            })
            return

        self._deny(404, "Not found")

    def do_POST(self):
        ip   = self.client_address[0]
        host = self.headers.get("Host", "")

        if is_rate_limited(ip):
            self._deny(429, "Rate limited")
            return

        if not is_local_host(host):
            record_bad(ip)
            self._deny(403, "Invalid host")
            return

        if not self.check_token():
            record_bad(ip)
            self._deny(403, "Forbidden")
            return

        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body        = self.rfile.read(content_len)

        try:
            data = json.loads(body)
        except Exception:
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        if path == "/api/entries":
            required = ["id", "tool", "category", "observation"]
            if not all(k in data for k in required):
                self.send_json({"error": "Missing fields"}, 400)
                return
            entries = load_entries()
            if any(e.get("id") == data["id"] for e in entries):
                self.send_json({"ok": True, "note": "duplicate"})
                return
            entries.insert(0, data)
            save_entries(entries)
            self.send_json({"ok": True, "total": len(entries)})
            return

        self._deny(404, "Not found")

    def do_DELETE(self):
        ip   = self.client_address[0]
        host = self.headers.get("Host", "")

        if is_rate_limited(ip):
            self._deny(429, "Rate limited")
            return

        if not is_local_host(host):
            record_bad(ip)
            self._deny(403, "Invalid host")
            return

        if not self.check_token():
            record_bad(ip)
            self._deny(403, "Forbidden")
            return

        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        if path.startswith("/api/entries/"):
            try:
                entry_id = int(path.split("/")[-1])
            except ValueError:
                self.send_json({"error": "Invalid ID"}, 400)
                return
            entries = load_entries()
            before  = len(entries)
            entries = [e for e in entries if e.get("id") != entry_id]
            if len(entries) == before:
                self.send_json({"error": "Not found"}, 404)
                return
            save_entries(entries)
            self.send_json({"ok": True, "total": len(entries)})
            return

        self._deny(404, "Not found")

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"READY:{PORT}:{TOKEN}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
