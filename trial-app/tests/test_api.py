"""API + 保存層測試:用本機假的 Upstash REST 伺服器驗證『每個請求都重新載入資料庫』(模擬無伺服器冷啟動),完全不連真實服務。"""
import base64, gzip, importlib, json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest

DATA = {}


class FakeUpstash(BaseHTTPRequestHandler):
    def do_POST(self):
        assert self.headers["Authorization"] == "Bearer tok"
        cmd = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if cmd[0] == "SET": DATA[cmd[1]] = cmd[2]; out = {"result": "OK"}
        elif cmd[0] == "GET": out = {"result": DATA.get(cmd[1])}
        else: out = {"error": "ERR unknown"}
        b = json.dumps(out).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass


@pytest.fixture
def api(monkeypatch):
    DATA.clear()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstash); threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("KV_REST_API_URL", f"http://127.0.0.1:{srv.server_port}"); monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
    import store; importlib.reload(store)
    import api.index as m; importlib.reload(m)
    yield m
    srv.shutdown()


def call(m, op, body=None, **qs):
    return m.run(op, {k: [str(v)] for k, v in qs.items()}, body or {})


def test_state_persists_across_cold_starts_and_is_stored_compressed(api):
    q = call(api, "daily")
    assert len(q["items"]) == 5 and "answer_index" not in q["items"][0]
    assert call(api, "overview")["quizzes"][0]["id"] == q["id"]           # 新的請求 = 新的引擎,資料從 Redis 載回
    raw = DATA["la-trial:v1"]; assert len(base64.b64decode(raw)) < 200_000    # gzip 後遠小於免費方案單次請求上限
    assert gzip.decompress(base64.b64decode(raw))[:15] == b"SQLite format 3"


def test_full_flow_over_api_with_persistence(api):
    d = call(api, "daily"); qid = d["id"]
    with pytest.raises(ValueError): call(api, "submit", {"answers": [{"selected": 0}] * 3}, id=qid)
    res = call(api, "submit", {"answers": [{"selected": 0, "unsure": False}] * 5}, id=qid)
    assert all("explanation" in i for i in res["items"])
    wrong = [i for i in res["items"] if not i["correct"]]
    if wrong: call(api, "error_type", {"quiz_id": qid, "pos": wrong[0]["pos"], "type": "粗心"})
    n = call(api, "next"); assert n["id"] != qid and n["kind"] == "next"
    assert call(api, "next")["id"] == n["id"]                              # 只有一份未完成的額外測驗
    ov = call(api, "overview"); assert ov["storage"] == "redis" and len(ov["quizzes"]) == 2
    call(api, "advance_day"); assert call(api, "overview")["day"] == 2
    call(api, "reset"); assert call(api, "overview")["quizzes"] == []


def test_get_cannot_write(api):
    import io
    from api.index import handler
    class R(handler):
        def __init__(s): s.path = "/api/index?op=reset"; s.out = []; s.rfile = io.BytesIO(); s.wfile = io.BytesIO(); s.headers = {}
        def send_response(s, c, m=None): s.code = c
        def send_header(s, *a): pass
        def end_headers(s): pass
    r = R(); r.do_GET(); assert r.code == 405
    assert call(api, "overview")["quizzes"] == []


def test_ephemeral_mode_without_redis(monkeypatch, tmp_path):
    for k in ("KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"): monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TRIAL_DB", str(tmp_path / "x.db"))
    import store; importlib.reload(store)
    import api.index as m; importlib.reload(m)
    assert call(m, "overview")["storage"] == "ephemeral"
    call(m, "daily"); assert len(call(m, "overview")["quizzes"]) == 1
