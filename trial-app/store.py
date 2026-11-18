"""測試資料保存:整個 SQLite 資料庫序列化後 gzip+base64,存在『獨立的』Redis(Upstash,經 Vercel Marketplace 建立)的單一 key。
完全不連任何 Supabase。沒有設定 Redis 時退回本機檔案(只適合本機開發;Vercel 上會在畫面標示『資料會遺失』)。"""
import base64, gzip, json, os, urllib.request

KEY = os.environ.get("TRIAL_KEY", "la-trial:v1")
LOCAL = os.environ.get("TRIAL_DB", "/tmp/la_trial.db")


def _cfg():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    tok = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), tok) if url and tok else None


def mode() -> str:
    return "redis" if _cfg() else "ephemeral"


def _cmd(args):
    url, tok = _cfg()
    req = urllib.request.Request(url, data=json.dumps(args).encode(), headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        out = json.loads(r.read())
    if "error" in out: raise RuntimeError("storage error: " + str(out["error"])[:200])
    return out.get("result")


def load():
    if _cfg():
        v = _cmd(["GET", KEY])
        return gzip.decompress(base64.b64decode(v)) if v else None
    return open(LOCAL, "rb").read() if os.path.exists(LOCAL) else None


def save(blob: bytes) -> int:
    if _cfg():
        v = base64.b64encode(gzip.compress(blob, 6)).decode()
        _cmd(["SET", KEY, v]); return len(v)
    open(LOCAL, "wb").write(blob); return len(blob)
