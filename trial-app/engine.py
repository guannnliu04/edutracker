"""測試版引擎:產生五題 → 作答 → 解析 → 錯題紀錄 → 1/3/7 複習 → 下一份五題 → 自動調整難度。
完全獨立的 SQLite 檔,不連正式網站與 Supabase。時間用「虛擬日」(測試時可按『進入新的一天』快轉)。
所有題目一律先過 lagen 驗證器;未通過者絕不出給使用者;題目不足就如實少出並記錄。"""
import hashlib
import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lagen import dedup, pipeline, templates, validate
from lagen.taxonomy import BASIC_ELIGIBLE, TAXONOMY

HERE = Path(__file__).parent
ERROR_TYPES = ["觀念不清", "計算錯誤", "粗心", "看不懂題目", "完全不會", "其他"]
# 工程預設(決策紀錄見 DECISIONS.md)
CFG = {"review_offsets": [1, 3, 7], "dedup_days": 60, "near_days": 7, "max_reinforce": 2, "mode": "valid_day_sequence"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS quizzes(id INTEGER PRIMARY KEY, kind TEXT, day INT, level INT, base_difficulty INT, plan TEXT,
  created_at REAL, submitted_at REAL, score INT, unsure_correct INT);
CREATE TABLE IF NOT EXISTS items(quiz_id INT, pos INT, q TEXT, concept TEXT, role TEXT, source TEXT, angle TEXT, difficulty INT,
  review_id INT, selected INT, correct INT, unsure INT, error_type TEXT, PRIMARY KEY(quiz_id,pos));
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, concept TEXT, role TEXT, stage INT, due_day INT, done INT DEFAULT 0, origin_quiz INT);
CREATE TABLE IF NOT EXISTS error_history(id INTEGER PRIMARY KEY, quiz_id INT, pos INT, old_type TEXT, new_type TEXT, changed_at REAL);
CREATE TABLE IF NOT EXISTS gen_log(id INTEGER PRIMARY KEY, quiz_id INT, pos INT, stage TEXT, code TEXT, detail TEXT);
"""


# ───────── 規則(與 rules.ts 原型一致) ─────────
def composition(level: int, basic_need: bool = False) -> Dict[str, int]:
    return {1: {"basic": 3, "progress": 1, "bank": 1}, 2: {"basic": 2, "progress": 1, "bank": 2}, 3: {"basic": 1, "progress": 1, "bank": 3},
            4: {"basic": 1, "progress": 1, "bank": 3} if basic_need else {"basic": 0, "progress": 1, "bank": 4}}[level]


def review_count(due: int, new_section_boost: bool = False, all_fresh: bool = False) -> int:
    if all_fresh or due == 0: return 0
    if due >= 3: return 3
    if new_section_boost and due <= 1: return 1
    return 2


def adjust(P: int, c: int, u: int) -> Dict[str, Any]:
    if c == 5 and u == 0: return {"base": min(4, P + 1), "advanced": 0, "reinforce": False, "foundation": False, "code": "PERFECT_UP" if P < 4 else "PERFECT_AT_MAX"}
    if c in (4, 5): return {"base": P, "advanced": 1 if P < 4 else 0, "reinforce": False, "foundation": False, "code": "PERFECT_BUT_UNSURE" if c == 5 else "FOUR_OF_FIVE"}
    if c == 3: return {"base": P, "advanced": 0, "reinforce": True, "foundation": False, "code": "THREE_OF_FIVE"}
    return {"base": max(1, P - 1), "advanced": 0, "reinforce": True, "foundation": True, "code": "LOW_DOWN" if P > 1 else "LOW_AT_MIN"}


def evaluate_level(days: List[Dict[str, Any]], start: int = 1):
    """days:每個測驗日『第一份每日測驗』的結果(N5),依日期排序;只含已完成的有效日(N1:缺席不中斷)。"""
    level, window, log = start, [], []
    acc = lambda d: sum(q["correct"] for q in d["qs"]) / len(d["qs"])
    b_ok = lambda d: all(q["correct"] for q in d["qs"] if q["role"] == "basic")
    b_nu = lambda d: all(not q["unsure"] for q in d["qs"] if q["role"] == "basic")
    def no_repeat(ds):
        m: Dict[str, set] = {}
        for d in ds:
            for q in d["qs"]:
                if q["role"] == "basic" and not q["correct"]: m.setdefault(q["concept"], set()).add(d["day"])
        return all(len(s) < 2 for s in m.values())
    for d in sorted(days, key=lambda x: x["day"]):
        if len(d["qs"]) != 5: continue  # 題數不足 = 中性日
        window.append(d); last = lambda n: window[-n:]
        if len(window) >= 2 and all(acc(x) < 0.6 for x in last(2)) and level > 1:
            log.append({"day": d["day"], "from": level, "to": level - 1, "why": "連續2日<60%"}); level -= 1; window = []; continue
        if level == 1 and len(window) >= 3 and all(b_ok(x) and b_nu(x) for x in last(3)): log.append({"day": d["day"], "from": 1, "to": 2, "why": "連3日基礎全對且基礎無不確定"}); level, window = 2, []
        elif level == 2 and len(window) >= 3 and all(acc(x) >= .8 and b_ok(x) for x in last(3)): log.append({"day": d["day"], "from": 2, "to": 3, "why": "連3日≥80%且基礎全對"}); level, window = 3, []
        elif level == 3 and len(window) >= 5 and all(acc(x) >= .8 for x in last(5)) and no_repeat(last(5)): log.append({"day": d["day"], "from": 3, "to": 4, "why": "連5日≥80%且無反覆基礎錯誤"}); level, window = 4, []
    return level, log


# ───────── 題源 ─────────
def _tpl_info():
    info: Dict[str, List] = {}
    for tid in templates.TEMPLATES:
        q = templates.make(tid, 0, 2, "basic")
        info.setdefault(q["concept"], []).append((tid, q["angle"]))
    return info


TPL = _tpl_info()
AI_POOL: List[dict] = json.load(open(HERE / "ai_candidates.json", encoding="utf8"))
ALL_CONCEPTS = sorted(set(TPL) | {c["concept"] for c in AI_POOL})


class Engine:
    def __init__(self, path: str = "trial.db", ai_gen: Optional[Callable[[dict], Optional[dict]]] = None, blob: Optional[bytes] = None):
        self.db = sqlite3.connect(":memory:" if blob is not None else path, check_same_thread=False)
        if blob is not None: self.db.deserialize(blob)   # 無伺服器環境:整個資料庫由外部儲存載入,不依賴本機檔案
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.ai_gen = ai_gen  # 路線 B(OpenAI)之後接在這裡;簽名 ai_gen(request) -> candidate dict | None
        if self.get("day") is None: self.set("day", 1); self.set("level", 1); self.set("learned", sorted(set(TAXONOMY.values())))

    def to_blob(self) -> bytes:
        self.db.commit(); return self.db.serialize()

    # state helpers
    def get(self, k, default=None):
        r = self.db.execute("select v from state where k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default

    def set(self, k, v):
        self.db.execute("insert or replace into state values(?,?)", (k, json.dumps(v))); self.db.commit()

    def reset(self):
        for t in ("state", "quizzes", "items", "reviews", "error_history", "gen_log"): self.db.execute(f"delete from {t}")
        self.db.commit(); self.set("day", 1); self.set("level", 1); self.set("learned", sorted(set(TAXONOMY.values())))

    # ───── 弱點與近期題目 ─────
    def weak(self) -> Dict[str, int]:
        w: Dict[str, int] = {}
        for r in self.db.execute("select concept, correct, unsure from items where correct is not null"):
            if not r["correct"]: w[r["concept"]] = w.get(r["concept"], 0) + 2
            elif r["unsure"]: w[r["concept"]] = w.get(r["concept"], 0) + 1
        return w

    def _recent_ctx(self, request: dict) -> validate.Ctx:
        day = self.get("day")
        recent = []
        for r in self.db.execute("select q, quizzes.day as d from items join quizzes on quizzes.id=items.quiz_id"):
            q = json.loads(r["q"]); recent.append({**dedup.fingerprints(q), "day": r["d"]})
        return validate.Ctx(taxonomy=TAXONOMY, learned_sections=set(self.get("learned")), request=request, recent=recent, today=day,
                            dedup_cfg={"param_days": CFG["dedup_days"], "near_days": CFG["near_days"]})

    def _recent_angles(self, concept: str) -> List[str]:
        return [r["angle"] for r in self.db.execute("select angle from items join quizzes on quizzes.id=items.quiz_id where concept=? order by quizzes.id, pos", (concept,))]

    # ───── 出一格題:階梯 AI 題池 → 參數化模板 → (題庫,之後) ─────
    def _fill(self, req: dict, seed: int, quiz_id: int, pos: int, ctx_extra: List[dict]):
        concept = req["concept"]
        recent_angles = self._recent_angles(concept)
        # ① AI 候選題(路線 A 為手寫候選;路線 B 由 OpenAI 即時產生,仍走同一個驗證器)
        cands = [c for c in AI_POOL if c["concept"] == concept and c["role"] == req["role"] and abs(c["difficulty"] - req["difficulty"]) <= 1]
        if self.ai_gen:
            try:
                g = self.ai_gen(req)
                if g: cands = [g] + cands
            except Exception as e:  # noqa: BLE001
                self._log(quiz_id, pos, "AI_CALL", "AI_ERROR", f"{type(e).__name__}: {e}")
        cands.sort(key=lambda c: (c["angle"] in recent_angles, recent_angles.index(c["angle"]) if c["angle"] in recent_angles else -1))
        for c in cands:
            ctx = self._recent_ctx({**req, "difficulty": c["difficulty"], "review_variant": bool(req.get("review_variant"))}); ctx.recent += ctx_extra
            r = validate.validate_candidate(c, ctx)
            if r.ok: return {**c, "difficulty": c["difficulty"]}
            for f in r.failures: self._log(quiz_id, pos, f["stage"], f["code"], f["detail"])
        # ② 參數化模板:同觀念輪替角度(最久沒用的角度優先)
        tpls = TPL.get(concept, [])
        order = sorted(tpls, key=lambda t: (recent_angles.index(t[1]) if t[1] in recent_angles else -1))
        # 同一角度的最近使用位置 → 越久沒用越先
        last = {a: max([i for i, x in enumerate(recent_angles) if x == a], default=-1) for _, a in tpls}
        order = sorted(tpls, key=lambda t: last[t[1]])
        for tid, _ang in order:
            for k in range(4):
                ctx = self._recent_ctx(dict(req)); ctx.recent += ctx_extra
                c, _n, fails = templates.make_valid(tid, seed + k, req["difficulty"], req["role"], ctx, tries=3)
                if c is not None: return c
                for f in fails[:2]: self._log(quiz_id, pos, f["stage"], f["code"], f["detail"])
        return None

    def _log(self, quiz_id, pos, stage, code, detail):
        self.db.execute("insert into gen_log(quiz_id,pos,stage,code,detail) values(?,?,?,?,?)", (quiz_id, pos, stage, code, detail[:300]))

    # ───── 建立測驗 ─────
    def _rank_concepts(self, role: str, used: List[str]) -> List[str]:
        pool = [c for c in ALL_CONCEPTS if (role != "basic" or c in BASIC_ELIGIBLE)]
        weak = self.weak()
        lastseen = {c: -1 for c in pool}
        for r in self.db.execute("select concept, quiz_id from items"): lastseen[r["concept"]] = max(lastseen.get(r["concept"], -1), r["quiz_id"])
        return sorted(pool, key=lambda c: (c in used, -weak.get(c, 0) if weak.get(c, 0) >= 2 else 0, lastseen.get(c, -1), c))

    def _pick_concept(self, role: str, used: List[str], prefer: List[str]) -> Optional[str]:
        pool = [c for c in ALL_CONCEPTS if (role != "basic" or c in BASIC_ELIGIBLE)]
        for c in prefer:
            if c in pool and c not in used: return c
        weak = self.weak()
        # 弱點優先,其次是最久沒練的觀念
        lastseen = {c: -1 for c in pool}
        for r in self.db.execute("select concept, quiz_id from items"): lastseen[r["concept"]] = max(lastseen.get(r["concept"], -1), r["quiz_id"])
        cand = [c for c in pool if c not in used] or pool
        return sorted(cand, key=lambda c: (-weak.get(c, 0) if weak.get(c, 0) >= 2 else 0, lastseen.get(c, -1), c))[0] if cand else None

    def create_quiz(self, kind: str, base: int, level: int, *, reinforce: Optional[List[str]] = None, advanced: int = 0, adjust_code: str = "", foundation: bool = False) -> dict:
        day = self.get("day")
        due = [dict(r) for r in self.db.execute("select * from reviews where done=0 and due_day<=? order by due_day, id", (day,))]
        comp = composition(base, any(d["role"] == "basic" for d in due))
        roles = ["basic"] * comp["basic"] + ["progress"] * comp["progress"] + ["bank"] * comp["bank"]
        n_rev = review_count(len(due))
        slots = [{"role": r, "review": None, "reinforce": False, "diff": base} for r in roles]
        used_rev = set()
        for d in due:  # 複習只能放進同角色格子;沒被選到的維持到期
            if len(used_rev) >= n_rev: break
            s = next((s for s in slots if s["role"] == d["role"] and s["review"] is None), None)
            if s: s["review"] = d; used_rev.add(d["id"])
        left = [d["id"] for d in due if d["id"] not in used_rev]
        rf = list(reinforce or [])[:CFG["max_reinforce"]]
        for c in rf:  # 加強:出同觀念變式,角色需相容,不占複習格
            s = next((s for s in slots if s["review"] is None and not s["reinforce"] and (s["role"] != "basic" or c in BASIC_ELIGIBLE)), None)
            if s: s["reinforce"] = c
        if advanced:  # N11:題庫格優先、其次進度格,不動基礎格
            s = next((s for s in slots if s["role"] == "bank" and not s["review"] and not s["reinforce"]), None) or next((s for s in slots if s["role"] == "progress" and not s["review"] and not s["reinforce"]), None)
            if s: s["diff"] = min(4, base + 1)
        cur = self.db.execute("insert into quizzes(kind,day,level,base_difficulty,plan,created_at) values(?,?,?,?,?,?)", (kind, day, level, base, "{}", time.time()))
        qid = cur.lastrowid
        used, items, shortages, extra = [], [], [], []
        for pos, s in enumerate(slots):
            fixed = s["review"]["concept"] if s["review"] else s["reinforce"]
            tries = [fixed] if fixed else self._rank_concepts(s["role"], used)[:6]   # 該觀念這次出不出題 → 換下一個觀念,不硬補未驗證題
            seed = int(hashlib.sha256(f"{qid}:{pos}:{day}".encode()).hexdigest()[:8], 16) % 100000
            q = None
            for concept in tries:
                req = {"role": s["role"], "difficulty": s["diff"], "concept": concept, "review_variant": bool(s["review"] or s["reinforce"])}
                q = self._fill(req, seed, qid, pos, extra)
                if q is not None: break
            if q is None:
                shortages.append({"pos": pos, "request": req}); self._log(qid, pos, "ASSEMBLE", "SHORTAGE", json.dumps(req, ensure_ascii=False)); continue
            fq = validate.finalize(q); fq["difficulty"] = q["difficulty"]
            extra.append({**dedup.fingerprints(q), "day": day}); used.append(concept)
            self.db.execute("insert into items(quiz_id,pos,q,concept,role,source,angle,difficulty,review_id) values(?,?,?,?,?,?,?,?,?)",
                            (qid, pos, json.dumps(fq, ensure_ascii=False), q["concept"], s["role"], q["source"], q["angle"], q["difficulty"], s["review"]["id"] if s["review"] else None))
            items.append(pos)
        plan = {"composition": comp, "n_review": len(used_rev), "reinforce": rf, "advanced": advanced, "adjust_code": adjust_code, "foundation": foundation,
                "leftover_due": left, "shortages": shortages, "ratio": f"{5 - len(used_rev)}+{len(used_rev)}"}
        self.db.execute("update quizzes set plan=? where id=?", (json.dumps(plan, ensure_ascii=False), qid)); self.db.commit()
        return self.quiz_view(qid)

    def create_daily(self) -> dict:
        day = self.get("day")
        r = self.db.execute("select id from quizzes where kind='daily' and day=?", (day,)).fetchone()
        if r: return self.quiz_view(r["id"])  # 冪等:每天只有一份每日測驗
        level, _ = self.level_state()
        self.set("level", level)
        return self.create_quiz("daily", level, level)

    def create_next(self) -> dict:
        open_q = self.db.execute("select id from quizzes where submitted_at is null and kind='next'").fetchone()
        if open_q: return self.quiz_view(open_q["id"])  # 同時只有一份未完成的額外測驗
        last = self.db.execute("select * from quizzes where submitted_at is not null order by id desc limit 1").fetchone()
        level, _ = self.level_state()
        if not last: return self.create_quiz("next", level, level, adjust_code="NO_PREVIOUS")
        a = adjust(last["base_difficulty"], last["score"], last["unsure_correct"])
        wrong = [r["concept"] for r in self.db.execute("select concept from items where quiz_id=? and correct=0 order by pos", (last["id"],))]
        unsure = [r["concept"] for r in self.db.execute("select concept from items where quiz_id=? and correct=1 and unsure=1", (last["id"],))]
        rf = (wrong if a["reinforce"] else [])
        return self.create_quiz("next", a["base"], level, reinforce=rf or None, advanced=a["advanced"], adjust_code=a["code"], foundation=a["foundation"])

    def level_state(self):
        days = []
        for r in self.db.execute("select id, day from quizzes where kind='daily' and submitted_at is not null order by day"):
            qs = [{"correct": bool(i["correct"]), "unsure": bool(i["unsure"]), "role": i["role"], "concept": i["concept"]}
                  for i in self.db.execute("select * from items where quiz_id=? order by pos", (r["id"],))]
            days.append({"day": r["day"], "qs": qs})
        return evaluate_level(days)

    # ───── 檢視與作答 ─────
    def quiz_view(self, qid: int) -> dict:
        qz = self.db.execute("select * from quizzes where id=?", (qid,)).fetchone()
        done = qz["submitted_at"] is not None
        items = []
        for r in self.db.execute("select * from items where quiz_id=? order by pos", (qid,)):
            q = json.loads(r["q"])
            it = {"pos": r["pos"], "concept": r["concept"], "role": r["role"], "source": r["source"], "angle": r["angle"], "difficulty": r["difficulty"],
                  "is_review": r["review_id"] is not None, "stem": q["stem"], "options": q["option_texts"]}
            if done:  # 全部提交後才揭露答案與解析
                it.update({"answer_index": q["answer_index"], "explanation": q["explanation"], "selected": r["selected"], "correct": bool(r["correct"]),
                           "unsure": bool(r["unsure"]), "error_type": r["error_type"]})
            items.append(it)
        return {"id": qid, "kind": qz["kind"], "day": qz["day"], "level": qz["level"], "base_difficulty": qz["base_difficulty"], "submitted": done,
                "score": qz["score"], "plan": json.loads(qz["plan"]), "items": items}

    def submit(self, qid: int, answers: List[Dict[str, Any]]) -> dict:
        qz = self.db.execute("select * from quizzes where id=?", (qid,)).fetchone()
        if qz is None: raise ValueError("no such quiz")
        if qz["submitted_at"] is not None: return self.quiz_view(qid)  # 重複提交不重複計算
        rows = list(self.db.execute("select * from items where quiz_id=? order by pos", (qid,)))
        if len(answers) != len(rows) or any(a.get("selected") not in (0, 1, 2, 3) for a in answers):
            raise ValueError("必須五題都作答才能交卷")  # 答案揭露條件:全部提交
        score = unsure_c = 0
        day = self.get("day")
        for r, a in zip(rows, answers):
            q = json.loads(r["q"]); ok = a["selected"] == q["answer_index"]; u = bool(a.get("unsure"))
            score += ok; unsure_c += ok and u
            self.db.execute("update items set selected=?, correct=?, unsure=? where quiz_id=? and pos=?", (a["selected"], int(ok), int(u), qid, r["pos"]))
            if r["review_id"]:
                if ok: self.db.execute("update reviews set done=1 where id=?", (r["review_id"],))
            if not ok:  # 錯題:排 1/3/7 複習(同觀念只保留最新一組)
                self.db.execute("delete from reviews where concept=? and done=0", (r["concept"],))
                for i, off in enumerate(CFG["review_offsets"]):
                    self.db.execute("insert into reviews(concept,role,stage,due_day,origin_quiz) values(?,?,?,?,?)", (r["concept"], r["role"], off, day + off, qid))
        self.db.execute("update quizzes set submitted_at=?, score=?, unsure_correct=? where id=?", (time.time(), score, unsure_c, qid)); self.db.commit()
        return self.quiz_view(qid)

    def set_error_type(self, qid: int, pos: int, new_type: str):
        if new_type not in ERROR_TYPES: raise ValueError("bad error type")
        r = self.db.execute("select error_type, correct from items where quiz_id=? and pos=?", (qid, pos)).fetchone()
        if r is None or r["correct"] != 0: raise ValueError("只有答錯的題目可以標錯誤類型")
        if r["error_type"] != new_type:  # 保留原始分類與修改歷史(只增不改)
            self.db.execute("insert into error_history(quiz_id,pos,old_type,new_type,changed_at) values(?,?,?,?,?)", (qid, pos, r["error_type"], new_type, time.time()))
            self.db.execute("update items set error_type=? where quiz_id=? and pos=?", (new_type, qid, pos))
        self.db.commit()

    def advance_day(self) -> dict:
        self.set("day", self.get("day") + 1)
        return self.create_daily()  # 模擬 08:00 排程:新的一天建立新的每日測驗(前一天未完成的不被覆蓋)

    def overview(self) -> dict:
        level, log = self.level_state()
        qs = [dict(r) for r in self.db.execute("select id,kind,day,level,base_difficulty,score,submitted_at is not null as submitted from quizzes order by id desc limit 20")]
        due = [dict(r) for r in self.db.execute("select * from reviews where done=0 order by due_day")]
        return {"day": self.get("day"), "level": level, "level_log": log, "quizzes": qs, "reviews": due, "weak": self.weak(),
                "open_quiz": next((q["id"] for q in qs if not q["submitted"] and q["kind"] == "next"), None), "error_types": ERROR_TYPES}

    def gen_log(self, qid: int) -> List[dict]:
        return [dict(r) for r in self.db.execute("select pos,stage,code,detail from gen_log where quiz_id=?", (qid,))]
