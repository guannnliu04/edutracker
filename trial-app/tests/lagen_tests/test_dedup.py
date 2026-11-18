import copy

from lagen import dedup, pipeline, templates, validate


def recent_of(c, day):
    return {**dedup.fingerprints(c), "day": day}


def test_exact_duplicate_rejected(good, ctx):
    ctx.recent = [recent_of(good, 99)]
    r = validate.validate_candidate(copy.deepcopy(good), ctx)
    assert r.failures[0]["code"] == "DUP_CONTENT"


def test_same_math_with_reworded_stem_is_a_duplicate(good, ctx):
    ctx.recent = [recent_of(good, 90)]
    reworded = copy.deepcopy(good); reworded["stem_template"] = "請計算 {{A}} 這個矩陣的秩 $\\operatorname{rank}(A)$ 為多少。"
    r = validate.validate_candidate(reworded, ctx)
    assert r.failures[0]["code"] == "DUP_PARAMS"          # 只換敘述,數學內容相同 → 擋下


def test_same_concept_new_numbers_is_allowed_after_the_near_window(ctx):
    a = templates.make("rank_computation", 1, 2, "basic"); b = templates.make("rank_computation", 2, 2, "basic")
    ctx.recent = [recent_of(a, 100 - 30)]                  # 30 天前,已超過近似重複窗口
    assert validate.validate_candidate(b, ctx).ok


def test_near_duplicate_within_window_rejected_for_fresh_slots_but_allowed_for_review_variants(ctx):
    a = templates.make("rank_computation", 1, 2, "basic"); b = templates.make("rank_computation", 2, 2, "basic")
    a["source"] = b["source"] = "ai_generated"             # 近似重複只用在 AI 手寫文字題;參數化變式只換數字,見下一個測試
    ctx.recent = [recent_of(a, 99)]                        # 昨天才出過同結構、同題面、不同數字的題
    ctx.request = {"review_variant": False}
    assert validate.validate_candidate(b, ctx).failures[0]["code"] == "DUP_NEAR"
    ctx.request = {"review_variant": True}                 # 1/3/7 天複習的「同觀念變式」是被允許的
    assert validate.validate_candidate(b, ctx).ok


def test_different_angle_on_same_concept_is_not_near_duplicate(ctx):
    a = templates.make("independence_definition", 1, 2, "basic"); b = templates.make("independence_rref", 1, 2, "basic")
    assert a["concept"] == b["concept"] and a["angle"] != b["angle"]
    ctx.recent = [recent_of(a, 99)]
    assert validate.validate_candidate(b, ctx).ok


def test_angle_rotation_covers_all_angles_before_repeating():
    allowed = ["definition", "rref", "condition_change", "counterexample"]
    seen = []
    for _ in range(8):
        seen.append(pipeline.choose_angle(seen, allowed))
    assert set(seen[:4]) == set(allowed)                   # 前 4 次各用一個不同角度
    assert seen[4:] == seen[:4]                            # 之後依最久沒用的順序輪替


def test_text_similarity_masks_numbers():
    assert dedup.jaccard(dedup.normalize_text("求 {{A}} 的秩,A 為 3×4"), dedup.normalize_text("求 {{A}} 的秩,A 為 5×9")) == 1.0
    assert dedup.jaccard(dedup.normalize_text("判斷向量組是否線性獨立"), dedup.normalize_text("求矩陣的特徵值有哪些")) < 0.5


def test_param_variant_with_new_numbers_is_not_blocked_as_near_duplicate(ctx):
    """試用版發現:模板題題面本來就一樣,若套用近似重複會讓同觀念 7 天內完全出不了題。數學內容相同仍會被擋(見 DUP_PARAMS 測試)。"""
    a = templates.make("rank_computation", 1, 2, "basic"); b = templates.make("rank_computation", 2, 2, "basic")
    ctx.recent = [recent_of(a, 99)]
    assert validate.validate_candidate(b, ctx).ok


def test_content_hash_distinguishes_predicate_mode_questions(ctx):
    """試用版發現:預測式題型(選項內容在 objects/verifier)的 content_hash 曾經忽略選項,導致所有同模板題被視為完全相同。"""
    from lagen import dedup
    a = templates.make("basis_selection", 1, 1, "basic"); b = templates.make("basis_selection", 2, 1, "basic")
    assert dedup.fingerprints(a)["content_hash"] != dedup.fingerprints(b)["content_hash"]
