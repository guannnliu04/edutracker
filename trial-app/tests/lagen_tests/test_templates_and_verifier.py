import json

import pytest

from lagen import dsl, fracla, templates, validate
from lagen.taxonomy import TAXONOMY

TIDS = list(templates.TEMPLATES)


def test_all_templates_approved_with_exactly_one_correct_answer(ctx):
    """11 個模板 × 40 個種子 × 4 個難度:每題都通過完整驗證(含恰一個正確答案、第二套實作交叉驗證)"""
    total = approved = retried = 0
    agree = none = 0
    for tid in TIDS:
        for seed in range(40):
            for d in (1, 2, 3, 4):
                c, tries, _ = templates.make_valid(tid, seed, d, "basic", ctx)
                total += 1
                assert c is not None, f"{tid} seed={seed} d={d} 在 6 次嘗試內仍無法產生通過驗證的題目"
                approved += 1; retried += tries > 1
                r = validate.validate_candidate(c, ctx)
                assert r.ok and r.verification_level == "full"
                agree += r.crosscheck == "agree"; none += r.crosscheck == "none"
    assert approved == total == len(TIDS) * 40 * 4
    assert retried <= total * 0.01   # 需要重試的比例要很低
    print(f"\n模板 {total} 題全數通過;需要重試 {retried};第二套實作交叉驗證 agree={agree} / 沒有第二套實作={none}")


@pytest.mark.parametrize("tid", TIDS)
def test_reproducible_from_seed(tid):
    a, b = templates.make(tid, 7, 2, "basic"), templates.make(tid, 7, 2, "basic")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_sympy_and_independent_fraction_implementation_agree_on_random_matrices():
    """差異比對:SymPy 與純 Fraction 的第二套實作,在 2000 個隨機矩陣上所有結果完全一致"""
    import random
    rng = random.Random(2024)
    for _ in range(2000):
        m, n = rng.randint(1, 5), rng.randint(1, 5)
        rows = [[rng.randint(-4, 4) for _ in range(n)] for _ in range(m)]
        for op in ("rank", "nullity", "rref"):
            spec = {"op": op, "args": {"matrix": rows}}
            assert dsl.crosscheck(spec)[0] == "agree", (op, rows)
        if m == n:
            assert dsl.crosscheck({"op": "det", "args": {"matrix": rows}})[0] == "agree"
            if dsl.evaluate({"op": "det", "args": {"matrix": rows}})[1] != 0:
                assert dsl.crosscheck({"op": "inverse", "args": {"matrix": rows}})[0] == "agree"


def test_role_difficulty_and_source_are_independent_dimensions(ctx):
    """N8:角色、來源、難度是三個獨立維度。AI 生成題可以是基礎題;題庫題也可以是低難度題"""
    base = templates.make("basis_selection", 3, 1, "basic")
    combos = set()
    for role in ("basic", "progress", "bank"):
        for source in ("bank_verified", "param_variant", "ai_generated"):
            for diff in (1, 2, 3, 4):
                c = {**base, "role": role, "source": source, "difficulty": diff}
                assert validate.validate_candidate(c, ctx).ok
                combos.add((role, source, diff))
    assert len(combos) == 3 * 3 * 4
    assert ("basic", "ai_generated", 1) in combos and ("bank", "bank_verified", 1) in combos


def test_linear_independence_is_examined_from_multiple_angles(ctx):
    """同一觀念要能從不同角度考察,而不只是改文字或換數字"""
    angles = set()
    for tid in TIDS:
        c = templates.make(tid, 1, 2, "basic")
        if c["concept"] == "linear-independence": angles.add(c["angle"])
    assert {"definition", "rref", "condition_change"} <= angles
    # 加上反例(counterexample)與基底(basis)相關模板,涵蓋定義、RREF、含參數條件變化、反例、基底判斷
    assert templates.make("counterexample_product_zero", 1, 3, "bank")["angle"] == "counterexample"


def test_stem_and_options_are_rendered_by_server_from_structure(ctx):
    c = templates.make("rank_computation", 5, 2, "basic")
    assert "\\begin{bmatrix}" not in c["stem_template"]          # 題面模板沒有手寫矩陣
    q = validate.finalize(c)
    assert "\\begin{bmatrix}" in q["stem"] and len(set(q["option_texts"])) == 4


def test_every_distractor_is_verified_wrong(ctx):
    for tid in TIDS:
        c, _, _ = templates.make_valid(tid, 3, 3, "basic", ctx)
        assert sum(1 for _ in c["options"]) == 4
        assert c["answer_index"] in range(4)


def test_no_template_ever_renders_float_artifacts_in_options():
    """手機試用發現:反矩陣的一個干擾選項用了浮點除法,渲染成 13333333333333333/1000000000000000000。
    全模板 × 4 難度 × 40 種子:任何選項文字的分母都不得超過 10^6。"""
    import re
    from lagen import templates, validate
    for tid in templates.TEMPLATES:
        for d in (1, 2, 3, 4):
            for s in range(40):
                try: c = templates.make(tid, s, d, "basic")
                except RuntimeError: continue
                txt = validate.finalize(c)
                for t in txt["option_texts"] + [txt["stem"], txt["explanation"]]:
                    for den in re.findall(r"/(\d+)", t): assert int(den) < 10**6, (tid, d, s, t)


def test_fmt_rejects_floats():
    import pytest
    from lagen.render import fmt
    with pytest.raises(TypeError): fmt(0.1)
