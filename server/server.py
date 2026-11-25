#!/usr/bin/env python3
"""그림몬 명예의 전당 서버 (표준 라이브러리 + SQLite). 실행: python3 server.py"""
import json, sqlite3, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
KEY, PORT = "hub", 8080     # ← 클라이언트 config.SERVER_KEY 와 동일하게
db = sqlite3.connect("board.db", check_same_thread=False); lock = threading.Lock()
db.execute("create table if not exists b(uid text primary key,name text,cm real,grid text)")

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.headers.get("X-Key") != KEY or self.path != "/board": return self._send(403, {})
        with lock: rows = db.execute("select uid,name,cm,grid from b order by cm desc limit 50").fetchall()
        self._send(200, [{"uid": r[0], "name": r[1], "cm": r[2], "grid": r[3]} for r in rows])
    def do_POST(self):
        if self.headers.get("X-Key") != KEY or self.path != "/submit": return self._send(403, {})
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > 4000: return self._send(413, {})
            d = json.loads(self.rfile.read(n))
            uid, name, cm, grid = str(d["uid"])[:64], str(d["name"])[:20], float(d["cm"]), str(d["grid"])
            assert len(grid) == 1024 and 0 <= cm < 1e9
        except Exception: return self._send(400, {})
        with lock:   # 기록은 줄어들지 않게 max 유지
            db.execute("insert into b values(?,?,?,?) on conflict(uid) do update set name=excluded.name,"
                       "cm=max(cm,excluded.cm),grid=excluded.grid", (uid, name, cm, grid)); db.commit()
        self._send(200, {"ok": 1})
    def log_message(self, *a): pass

ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
