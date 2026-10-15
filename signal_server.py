# language: Python, file: signal_server.py, target: Python 3.8+
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, threading

STREAMS = {}
LOCK = threading.Lock()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n).decode())
        sid = data["stream"]
        with LOCK:
            s = STREAMS.setdefault(sid, {"offer": None, "candidates": [], "answer": None, "mac_candidates": []})
            t = data["type"]
            if t == "offer": s["offer"] = data["payload"]
            elif t == "candidate": s["candidates"].append(data["payload"])
            elif t == "answer": s["answer"] = data["payload"]
            elif t == "mac_candidate": s["mac_candidates"].append(data["payload"])
        self._json({"ok": True})

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        p = urlparse(self.path)
        if p.path == "/streams":
            with LOCK:
                self._json({k: {"has_offer": bool(v["offer"])} for k, v in STREAMS.items()})
            return
        q = parse_qs(p.query)
        sid = q.get("stream", [""])[0]
        with LOCK:
            self._json(STREAMS.get(sid, {}))

if __name__ == "__main__":
    print("signal server on :8888")
    import os
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), H).serve_forever()
