"""Vercel Python 函式:單一入口 /api/index?op=...。每個請求都從儲存載入資料庫、處理、(寫入類操作)再存回。
資料存放在獨立 Redis,不連任何 Supabase。"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import store  # noqa: E402
from engine import Engine  # noqa: E402

WRITES = {"daily", "next", "advance_day", "reset", "submit", "error_type"}


def run(op: str, qs: dict, body: dict):
    blob = store.load()
    eng = Engine(blob=blob) if blob is not None else Engine(blob=None, path=":memory:")
    if op == "overview": out = {**eng.overview(), "storage": store.mode()}
    elif op == "quiz":
        qid = int(qs["id"][0]); out = {**eng.quiz_view(qid), "gen_log": eng.gen_log(qid)}
    elif op == "daily": out = eng.create_daily()
    elif op == "next": out = eng.create_next()
    elif op == "advance_day": out = eng.advance_day()
    elif op == "reset": eng.reset(); out = {"ok": True}
    elif op == "submit": out = eng.submit(int(qs["id"][0]), body["answers"])
    elif op == "error_type": eng.set_error_type(int(body["quiz_id"]), int(body["pos"]), body["type"]); out = {"ok": True}
    elif op == "health": out = {"ok": True, "storage": store.mode()}
    else: raise ValueError("unknown op")
    if op in WRITES: out["_saved_bytes"] = store.save(eng.to_blob())
    return out


class handler(BaseHTTPRequestHandler):
    def _reply(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def _go(self, method):
        try:
            u = urlparse(self.path); qs = parse_qs(u.query); op = (qs.get("op") or ["health"])[0]
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
            if method == "GET" and op in WRITES: return self._reply(405, {"error": "use POST"})
            self._reply(200, run(op, qs, body))
        except Exception as e:  # noqa: BLE001
            self._reply(400, {"error": f"{type(e).__name__}: {e}"[:300]})

    def do_GET(self): self._go("GET")
    def do_POST(self): self._go("POST")
    def log_message(self, *a): pass
