import copy

import pytest

from lagen import dedup, pipeline, templates, validate
from lagen.pipeline import AIUnavailable, Budget, FailureLog

REQ = {"role": "basic", "difficulty": 2, "concept": "rank", "allowed_angles": ["rank", "computation"]}


def flawed(c):
    c = copy.deepcopy(c); c["answer_index"] = (c["answer_index"] + 1) % 4; return c


def make_ai(seq, base):
    """模擬 AI:依序回傳指定行為('bad' / 'good' / 'down')。沒有真的呼叫任何 API。"""
    state = {"n": 0}
    def gen(request, attempt):
        b = seq[min(state["n"], len(seq) - 1)]; state["n"] += 1
        if b == "down": raise TimeoutError("模擬 AI 逾時")
        c = copy.deepcopy(base); c["source"] = "ai_generated"
        return flawed(c) if b == "bad" else c
    gen.calls = state
    return gen


@pytest.fixture
def base(ctx):
    return templates.make("rank_computation", 11, 2, "basic")


def test_retry_succeeds_on_third_attempt_and_logs_two_failures(base, ctx):
    log, budget = FailureLog(), Budget(1.0)
    out = pipeline.generate_verified(REQ, make_ai(["bad", "bad", "good"], base), ctx, budget, log, max_attempts=3)
    assert out is not None and out["source"] == "ai_generated"
    assert [r["attempt"] for r in log.records] == [1, 2] and all(r["code"] == "ANSWER_KEY_MISMATCH" for r in log.records)
    assert budget.calls == 3


def test_retry_limit_is_enforced(base, ctx):
    log, budget = FailureLog(), Budget(1.0)
    ai = make_ai(["bad"], base)
    assert pipeline.generate_verified(REQ, ai, ctx, budget, log, max_attempts=3) is None
    assert ai.calls["n"] == 3 and budget.calls == 3 and len(log.records) == 3        # 絕不超過上限


def test_ai_outage_does_not_retry_and_falls_back_immediately(base, ctx):
    log, budget = FailureLog(), Budget(1.0)
    ai = make_ai(["down"], base)
    assert pipeline.generate_verified(REQ, ai, ctx, budget, log, max_attempts=3) is None
    assert ai.calls["n"] == 1 and log.records[0]["code"] == "AI_UNAVAILABLE"           # 斷路:不空等、不重試


def test_budget_cap_blocks_further_ai_calls(base, ctx):
    log, budget = FailureLog(), Budget(cap_usd=0.0010)                                   # 只夠 1 次(每次預留 0.0006)
    ai = make_ai(["bad"], base)
    assert pipeline.generate_verified(REQ, ai, ctx, budget, log, max_attempts=3) is None
    assert ai.calls["n"] == 1 and budget.spent <= 0.0010 and log.records[-1]["code"] == "BUDGET_EXHAUSTED"


def test_unverifiable_candidate_goes_to_review_queue_never_used(base, ctx):
    log, budget = FailureLog(), Budget(1.0)
    c = copy.deepcopy(base); c["verify_mode"] = "none"
    out = pipeline.generate_verified(REQ, lambda r, a: c, ctx, budget, log)
    assert out is None and len(log.review_queue) == 1 and log.records[0]["outcome"] == "needs_review"


def test_fallback_ladder_pool_then_template_then_bank(ctx):
    log = FailureLog()
    # ① 池裡有已驗證題 → 用池
    pool_q = templates.make("rank_computation", 21, 2, "basic"); pool_q["source"] = "ai_generated"
    q, src = pipeline.fill_slot(REQ, [pool_q], [], ctx, log)
    assert src == "ai_generated_pool"
    # ② 池空 → 模板
    ctx.recent = []
    q, src = pipeline.fill_slot(REQ, [], [], ctx, log)
    assert src == "param_variant" and q["source"] == "param_variant"
    # ③ 模板沒有這個觀念 → 題庫
    bank_q = templates.make("det3", 1, 2, "basic"); bank_q["source"] = "bank_verified"
    req2 = {"role": "basic", "difficulty": 2, "concept": "determinant"}
    ctx2 = validate.Ctx(taxonomy=ctx.taxonomy, learned_sections=ctx.learned_sections, today=ctx.today)
    q, src = pipeline.fill_slot(req2, [], [bank_q], ctx2, log)
    assert src in ("param_variant", "bank_verified") and q is not None


def test_shortage_is_reported_and_never_filled_with_unverified(base, ctx):
    log = FailureLog()
    bad = flawed(base)
    ctx.learned_sections = {"5.1"}                                       # 只學了秩
    reqs = [{"role": "basic", "difficulty": 2, "concept": "rank"}, {"role": "bank", "difficulty": 3, "concept": "eigenvalues"}] + [{"role": "basic", "difficulty": 2, "concept": "rank"}] * 3
    quiz, shortages = pipeline.assemble_quiz(reqs, [bad], [bad], ctx, log)
    assert len(quiz) + len(shortages) == 5 and shortages and shortages[0]["slot"] == 1     # 特徵值未學 → 缺口
    assert all(q["section"] in ctx.learned_sections for q in quiz)
    assert any(r["code"] == "SHORTAGE" for r in log.records)


def test_assemble_full_quiz_has_unique_math_and_respects_composition(ctx):
    """L2:2 基礎 + 1 進度 + 2 題庫。每一格都經驗證;同一份測驗內數學內容不重複"""
    log = FailureLog()
    reqs = [{"role": "basic", "difficulty": 2, "concept": "rank"}, {"role": "basic", "difficulty": 2, "concept": "linear-independence"},
            {"role": "progress", "difficulty": 2, "concept": "determinant"}, {"role": "bank", "difficulty": 2, "concept": "basis"}, {"role": "bank", "difficulty": 2, "concept": "matrix-properties"}]
    quiz, shortages = pipeline.assemble_quiz(reqs, [], [], ctx, log)
    assert len(quiz) == 5 and not shortages
    assert [q["role"] for q in quiz] == ["basic", "basic", "progress", "bank", "bank"]
    assert len({dedup.param_signature(q) for q in quiz}) == 5


def test_failure_report_aggregates_by_stage_and_code(base, ctx):
    log = FailureLog()
    for _ in range(2): pipeline.generate_verified(REQ, make_ai(["bad", "good"], base), ctx, Budget(1.0), log)
    assert log.report() == {("S3_recompute", "ANSWER_KEY_MISMATCH"): 2}


def test_unlearned_scope_is_never_bypassed_by_pregenerated_pool(ctx):
    ctx.learned_sections = {"1.2"}
    pool_q = templates.make("eigenvalues_2x2", 1, 3, "bank"); pool_q["source"] = "ai_generated"
    q, src = pipeline.fill_slot({"role": "bank", "difficulty": 3, "concept": "eigenvalues"}, [pool_q], [pool_q], ctx, FailureLog())
    assert q is None and src is None
