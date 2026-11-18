import copy
import os
import tempfile

import pytest

from lagen import dedup, templates, validate


def run(c, ctx):
    return validate.validate_candidate(c, ctx)


def code(r):
    return r.failures[0]["code"] if r.failures else None


def test_a_correct_candidate_is_approved(good, ctx):
    r = run(good, ctx)
    assert r.ok and r.verification_level == "full" and r.crosscheck == "agree" and r.fingerprints


def test_wrong_answer_key_is_rejected(good, ctx):
    good["answer_index"] = (good["answer_index"] + 1) % 4
    assert code(run(good, ctx)) == "ANSWER_KEY_MISMATCH"


def test_no_correct_option_is_rejected(good, ctx):
    wrong = copy.deepcopy(good["options"][(good["answer_index"] + 1) % 4])
    good["options"][good["answer_index"]] = {"claim": {"type": "int", "value": 99}}
    assert code(run(good, ctx)) == "NO_CORRECT_OPTION"


def test_two_correct_options_in_a_selection_question_are_rejected(ctx):
    c = templates.make("basis_selection", 2, 2, "basic")
    other = (c["answer_index"] + 1) % 4
    c["options"][other] = copy.deepcopy(c["options"][c["answer_index"]])    # 兩個選項都是基底
    assert code(run(c, ctx)) == "MULTIPLE_CORRECT_OPTIONS"


def test_duplicate_correct_values_are_rejected_before_they_reach_students(good, ctx):
    idx = good["answer_index"]; other = (idx + 1) % 4
    good["options"][other] = copy.deepcopy(good["options"][idx])
    assert code(run(good, ctx)) == "DUPLICATE_OPTION_TEXT"


def test_explanation_that_contradicts_the_answer_is_rejected(good, ctx):
    good["explanation_claim"] = {"type": "int", "value": 0}
    assert code(run(good, ctx)) == "EXPLANATION_MISMATCH"


def test_tampered_derived_object_is_rejected(good, ctx):
    good["objects"]["R"]["data"][0][0] = 7
    assert code(run(good, ctx)) == "DERIVED_OBJECT_MISMATCH"


def test_inconsistent_conditions_are_rejected(ctx):
    c = templates.make("inverse_2x2", 1, 2, "basic")
    c["objects"]["A"]["data"] = [[1, 2], [2, 4]]                           # 要求反矩陣,卻給奇異矩陣
    assert code(run(c, ctx)) == "PRECONDITION"
    d = templates.make("independence_definition", 1, 2, "basic")
    d["objects"]["V"]["data"] = [[1, 2, 3], [1, 2]]                        # 向量維度不一致
    assert code(run(d, ctx)) == "PRECONDITION"


def test_out_of_scope_concept_is_rejected(ctx):
    c = templates.make("eigenvalues_2x2", 1, 3, "bank")
    ctx.learned_sections = {s for s in ctx.learned_sections if s != "7.1"}
    assert code(run(c, ctx)) == "NOT_LEARNED_YET"


def test_not_using_unlearned_material_even_if_ai_can_generate_it(ctx):
    ctx.learned_sections = {"1.2", "1.3"}
    for tid in templates.TEMPLATES:
        c = templates.make(tid, 1, 2, "basic")
        assert not run(c, ctx).ok or c["section"] in ctx.learned_sections


@pytest.mark.parametrize("mismatch,expected", [({"difficulty": 4}, "DIFFICULTY_MISMATCH"), ({"role": "bank"}, "ROLE_MISMATCH"), ({"concept": "determinant"}, "CONCEPT_MISMATCH")])
def test_request_mismatch_is_rejected(good, ctx, mismatch, expected):
    ctx.request = {"difficulty": 2, "role": "basic", "concept": "rank", **mismatch}
    assert code(run(good, ctx)) == expected


def test_unknown_concept_and_section_mismatch(good, ctx):
    a = copy.deepcopy(good); a["concept"] = "made-up-concept"
    assert code(run(a, ctx)) == "UNKNOWN_CONCEPT"
    b = copy.deepcopy(good); b["section"] = "9.9"
    assert code(run(b, ctx)) == "SECTION_MISMATCH"


def test_incomplete_candidates_are_rejected(good, ctx):
    a = copy.deepcopy(good); a["options"].pop()
    assert code(run(a, ctx)) == "NOT_FOUR_OPTIONS"
    b = copy.deepcopy(good); b["explanation_template"] = ""
    assert code(run(b, ctx)) == "EMPTY_TEXT"
    c = copy.deepcopy(good); del c["objects"]; del c["stem_template"]
    assert code(run(c, ctx)) == "MISSING_FIELDS"


def test_hand_written_matrix_in_stem_is_rejected(good, ctx):
    good["stem_template"] = "設矩陣 \\begin{bmatrix}1&2\\\\3&4\\end{bmatrix},求其秩。"
    assert code(run(good, ctx)) == "RAW_MATRIX_IN_TEXT"


def test_proof_type_questions_are_not_auto_approved(good, ctx):
    good["verify_mode"] = "none"
    r = run(good, ctx)
    assert r.status == "needs_review" and not r.ok and code(r) == "UNVERIFIABLE_TYPE"


def test_partially_verifiable_questions_are_not_auto_approved(ctx):
    c = templates.make("eigenvalues_2x2", 1, 3, "bank")
    c["objects"]["A"]["data"] = [[2, 1], [1, 1]]                            # 特徵值是無理數
    r = run(c, ctx)
    assert r.status == "needs_review" and r.verification_level == "partial" and code(r) == "PARTIAL_ONLY"


def test_a_second_model_agreeing_does_not_make_wrong_math_correct(good, ctx):
    """『第二個 AI 認為答案正確』不是驗證:驗證流程不讀取這個旗標,答案錯就是錯"""
    good["answer_index"] = (good["answer_index"] + 1) % 4
    ctx.second_model_agrees = True
    assert code(run(good, ctx)) == "ANSWER_KEY_MISMATCH"


def test_hostile_specs_are_never_executed(good, ctx, tmp_path):
    marker = tmp_path / "pwned"
    good["verifier"] = {"op": f"__import__('os').system('touch {marker}')", "args": {}}
    assert code(run(good, ctx)) == "BAD_SPEC"
    assert not marker.exists()                                             # 絕不 eval / exec AI 產生的文字
    for evil in ({"op": "rank", "args": {"matrix": [[1, 2.5]]}}, {"op": "rank", "args": {"matrix": [[1] * 7] * 7}}, {"op": "rank", "args": {"matrix": [[10 ** 12]]}}, {"op": "rank", "args": {"matrix": "x"}}):
        c = copy.deepcopy(good); c["verifier"] = evil
        assert not run(c, ctx).ok


def test_validator_never_crashes_on_garbage(ctx):
    for garbage in ({}, {"concept": 1}, {"options": None}, {"concept": "rank", "section": "5.1", "role": "basic", "source": "ai_generated", "difficulty": 2, "angle": "rank", "stem_template": "x" * 20,
                                                          "verify_mode": "value", "options": [{"claim": 5}] * 4, "answer_index": 0, "explanation_template": "y" * 20, "verifier": {"op": "rank", "args": {"matrix": [[1]]}}}):
        r = run(garbage, ctx)
        assert not r.ok


def test_crosscheck_actually_detects_disagreement_between_the_two_implementations(good, ctx, monkeypatch):
    """補上的缺口:不只要證明『一致時通過』,也要證明『不一致時被抓到』(讓第二套實作故意算錯)"""
    from lagen import fracla
    monkeypatch.setattr(fracla, "rank", lambda m: 0)
    assert code(run(good, ctx)) == "CROSSCHECK_MISMATCH"


def test_equal_claims_always_render_to_identical_text_so_duplicates_cannot_hide():
    """為什麼數值型題目的『多個正確選項』會在更早一關被擋下:相等的 claim,不論怎麼表示,渲染出的文字必然相同"""
    from lagen.render import render_claim
    assert render_claim({"type": "rational", "value": "6/2"}) == render_claim({"type": "rational", "value": "3"}) == render_claim({"type": "int", "value": 3})
    assert render_claim({"type": "set_rational", "value": ["2", "1"]}) == render_claim({"type": "set_rational", "value": ["1", "2", "2"]})
    assert render_claim({"type": "matrix", "value": [["2/4", "1"]]}) == render_claim({"type": "matrix", "value": [["1/2", "1"]]})


def test_selection_question_with_no_satisfying_option_is_rejected(ctx):
    """補上的缺口:選擇題(predicate 模式)四個選項都不滿足條件時,必須被明確擋下"""
    c = templates.make("basis_selection", 4, 2, "basic")
    ans = c["answer_index"]
    c["options"][ans]["objects"]["S"]["data"] = [[1, 2, 3], [2, 4, 6], [3, 6, 9]]     # 把唯一的基底換成線性相依的向量組
    assert code(run(c, ctx)) == "NO_CORRECT_OPTION"
