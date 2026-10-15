"""Server don gian de thu giao tiep ESP32 <-> giao dien qua Wi-Fi.

Chay:  python server_don_gian.py      roi mo http://localhost:8000
ESP32 gui:  POST /api/line   noi dung  $CNT,<so_dem>,<dang_dem 0/1>,<millis>*CS
Trang web gui lenh: POST /api/cmd   {"cmd": "COUNT_ON" | "COUNT_OFF" | "COUNT_RESET"}
Lenh duoc xep hang va tra ve cho ESP32 trong phan hoi cua lan POST tiep theo.
Chi dung thu vien chuan cua Python.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
LENH = ("COUNT_ON", "COUNT_OFF", "COUNT_RESET")
MAT_KET_NOI_S = 3.0

lock = threading.Lock()
state = {"n": None, "dang_dem": None, "ts": 0.0, "loi_checksum": 0}
hang_lenh = []


def checksum(body):
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return "%02X" % cs


def doc_ban_tin(line):
    """Tra ve (so_dem, dang_dem) hoac None neu ban tin sai."""
    line = line.strip()
    if not line.startswith("$") or "*" not in line:
        return None
    body, _, cs = line[1:].rpartition("*")
    if checksum(body) != cs.strip().upper():
        return None
    f = body.split(",")
    if len(f) < 3 or f[0] != "CNT":
        return None
    try:
        return int(f[1]), f[2] == "1"
    except ValueError:
        return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def gui(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self.gui(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            with lock:
                age = time.time() - state["ts"] if state["ts"] else None
                self.gui(200, json.dumps({"n": state["n"], "dang_dem": state["dang_dem"], "tuoi": age,
                                          "ket_noi": age is not None and age < MAT_KET_NOI_S,
                                          "loi_checksum": state["loi_checksum"], "lenh_cho": list(hang_lenh)}))
        else:
            self.gui(404, '{"loi":"khong co"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("ascii", errors="ignore") if n else ""
        if self.path == "/api/line":
            for ln in raw.splitlines():
                if not ln.strip():
                    continue
                r = doc_ban_tin(ln)
                with lock:
                    if r is None:
                        state["loi_checksum"] += 1
                    else:
                        state.update(n=r[0], dang_dem=r[1], ts=time.time())
                        print(time.strftime("%H:%M:%S"), "ESP32: so dem =", r[0], "| dang dem =", r[1])
            with lock:
                cmd = hang_lenh.pop(0) if hang_lenh else ""
            if cmd:
                print(time.strftime("%H:%M:%S"), "gui lenh cho ESP32:", cmd)
            self.gui(200, json.dumps({"ok": True, "cmd": cmd}))
        elif self.path == "/api/cmd":
            try:
                cmd = json.loads(raw or "{}").get("cmd", "")
            except ValueError:
                cmd = ""
            with lock:
                ok = cmd in LENH and state["ts"] and time.time() - state["ts"] < MAT_KET_NOI_S
                if ok and cmd not in hang_lenh:
                    hang_lenh.append(cmd)
            self.gui(200 if ok else 409, json.dumps({"ok": bool(ok), "ly_do": "" if ok else "ESP32 chua ket noi hoac lenh sai"}))
        else:
            self.gui(404, '{"loi":"khong co"}')


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass          # trinh duyet dong tab giua chung: khong can in loi


if __name__ == "__main__":
    srv = Server(("0.0.0.0", 8000), Handler)
    print("Mo trinh duyet: http://localhost:8000   (Ctrl+C de dung)")
    print("ESP32 gui toi:   http://<IPv4 cua may nay>:8000/api/line")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
