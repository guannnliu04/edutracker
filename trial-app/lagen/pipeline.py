"""出題流程:預算、失敗紀錄、重試上限、備援階梯、組卷。
關鍵原則:任何未通過驗證(approved)的題目,絕不進入測驗;題目不足就如實少出並記錄原因。"""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import dedup, templates, validate


class Budget:
    """AI 預算。reserve() 在『呼叫前』預留額度;超過上限就拒絕(正式環境要用資料庫列鎖做成原子操作)"""
    def __init__(self, cap_usd: float):
        self.cap, self.spent, self.calls = cap_usd, 0.0, 0

    def reserve(self, est_usd: float) -> bool:
        if self.spent + est_usd > self.cap + 1e-12: return False
        self.spent += est_usd; self.calls += 1
        return True


@dataclass
class FailureLog:
    """驗證失敗與流程事件的追蹤紀錄(正式環境對應資料表 generation_failures)"""
    records: List[Dict[str, Any]] = field(default_factory=list)
    review_queue: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, *, request: dict, stage: str, code: str, detail: str, source: str, attempt: int, candidate: Optional[dict] = None, outcome: str = "rejected", model: str = "") -> None:
        key = hashlib.sha256(json.dumps(request, sort_keys=True, default=str).encode()).hexdigest()[:12]
        ch = hashlib.sha256(json.dumps(candidate, sort_keys=True, default=str).encode()).hexdigest()[:12] if candidate is not None else None
        self.records.append({"id": len(self.records) + 1, "request_key": key, "candidate_hash": ch, "source": source, "model": model, "attempt": attempt,
                             "stage": stage, "code": code, "detail": detail, "outcome": outcome})

    def report(self) -> Dict[Tuple[str, str], int]:
        """依 (階段, 代碼) 統計,用來判斷提示詞或模板該怎麼改"""
        return dict(Counter((r["stage"], r["code"]) for r in self.records))


class AIUnavailable(Exception):
    pass


def choose_angle(recent_angles: List[str], allowed: List[str]) -> str:
    """同一觀念輪替出題角度:優先選『最久沒用過』(或從沒用過)的角度"""
    last = {a: -1 for a in allowed}
    for i, a in enumerate(recent_angles):
        if a in last: last[a] = i
    return min(allowed, key=lambda a: last[a])


def generate_verified(request: dict, ai_gen: Callable[[dict, int], dict], ctx: validate.Ctx, budget: Budget, log: FailureLog, *, max_attempts: int = 3, est_usd: float = 0.0006) -> Optional[dict]:
    """預先生成流程(背景工作使用):AI 產生 → 驗證 → 失敗重試(有上限)。回傳通過驗證的題目或 None"""
    ctx.request = request
    for attempt in range(1, max_attempts + 1):
        if not budget.reserve(est_usd):
            log.add(request=request, stage="BUDGET", code="BUDGET_EXHAUSTED", detail=f"已花 {budget.spent:.4f} / 上限 {budget.cap:.4f}", source="ai_generated", attempt=attempt, outcome="skipped")
            return None
        try:
            cand = ai_gen(request, attempt)
        except (AIUnavailable, TimeoutError, ConnectionError) as e:
            log.add(request=request, stage="AI_CALL", code="AI_UNAVAILABLE", detail=type(e).__name__, source="ai_generated", attempt=attempt, outcome="skipped")
            return None  # 斷路:API 故障時不重試,立刻改用備援,避免使用者等待
        res = validate.validate_candidate(cand, ctx)
        if res.ok:
            return cand
        for f in res.failures:
            log.add(request=request, candidate=cand, source=cand.get("source", "ai_generated"), attempt=attempt, outcome=res.status, **f)
        if res.status == "needs_review":
            log.review_queue.append(cand)
            return None  # 無法自動驗證的題型:不重試、不使用,交人工審核
    return None


def _matches(cand: dict, request: dict) -> bool:
    return all(cand.get(k) == request[k] for k in ("role", "difficulty", "concept") if k in request)


def fill_slot(request: dict, pool: List[dict], bank: List[dict], ctx: validate.Ctx, log: FailureLog) -> Tuple[Optional[dict], Optional[str]]:
    """組卷時填一格,三步階梯,每一步都必須通過驗證:
    ① 已驗證快取池(含預先生成的 AI 題)→ ② 參數化模板 → ③ 已驗證題庫。
    組卷不會同步呼叫 AI,所以 AI 故障或變慢都不會影響出題速度。三處都沒有 → (None, None),由呼叫端記錄缺口。"""
    ctx.request = request
    for cand in pool:
        if _matches(cand, request) and validate.validate_candidate(cand, ctx).ok:
            return cand, "ai_generated_pool"
    c, _, _ = _try_template(request, ctx)
    if c is not None:
        return c, "param_variant"
    for cand in bank:
        if _matches(cand, request) and validate.validate_candidate(cand, ctx).ok:
            return cand, "bank_verified"
    return None, None


def _try_template(request: dict, ctx: validate.Ctx):
    cands = [tid for tid, f in templates.TEMPLATES.items() if _template_concept(tid) == request.get("concept")]
    for tid in cands:
        for seed in range(ctx.today * 7, ctx.today * 7 + 5):
            c, n, fails = templates.make_valid(tid, seed, request["difficulty"], request["role"], ctx, tries=3)
            if c is not None: return c, n, fails
    return None, 0, []


_CONCEPT_CACHE: Dict[str, str] = {}


def _template_concept(tid: str) -> str:
    if tid not in _CONCEPT_CACHE:
        _CONCEPT_CACHE[tid] = templates.make(tid, 0, 2, "basic")["concept"]
    return _CONCEPT_CACHE[tid]


def assemble_quiz(slot_requests: List[dict], pool: List[dict], bank: List[dict], ctx: validate.Ctx, log: FailureLog) -> Tuple[List[dict], List[dict]]:
    """依 5 個格子要求組卷。回傳 (題目清單, 缺口清單)。未通過驗證的題目絕不會出現在題目清單裡。"""
    quiz, shortages = [], []
    for i, req in enumerate(slot_requests):
        q, src = fill_slot(req, pool, bank, ctx, log)
        if q is None:
            shortages.append({"slot": i, "request": req, "reason": "NO_VERIFIED_QUESTION_AVAILABLE"})
            log.add(request=req, stage="ASSEMBLE", code="SHORTAGE", detail="已學範圍內沒有可用的已驗證題目", source="-", attempt=0, outcome="shortage")
            continue
        fp = dedup.fingerprints(q)
        ctx.recent.append({**fp, "day": ctx.today})  # 同一份測驗內也不重複
        quiz.append({**q, "_served_from": src})
    return quiz, shortages
