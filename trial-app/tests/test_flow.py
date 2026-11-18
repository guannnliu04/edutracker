import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from engine import Engine, adjust, composition, evaluate_level


@pytest.fixture
def eng(tmp_path):
    return Engine(str(tmp_path / "t.db"))


def answer_all(eng, view, wrong_n=0, unsure=False, wrong_positions=None):
    """用伺服器內部答案模擬作答:答對 5-wrong_n 題"""
    rows = list(eng.db.execute("select pos,q from items where quiz_id=? order by pos", (view["id"],)))
    wp = set(wrong_positions if wrong_positions is not None else range(wrong_n))
    ans = []
    for r in rows:
        k = json.loads(r["q"])["answer_index"]
        ans.append({"selected": (k + 1) % 4 if r["pos"] in wp else k, "unsure": unsure})
    return eng.submit(view["id"], ans)


def test_five_questions_and_composition(eng):
    v = eng.create_daily()
    assert len(v["items"]) == 5 and not v["plan"]["shortages"]
    roles = [i["role"] for i in v["items"]]
    assert (roles.count("basic"), roles.count("progress"), roles.count("bank")) == (3, 1, 1)  # Level 1


def test_answers_hidden_until_submitted(eng):
    v = eng.create_daily()
    assert all("answer_index" not in i and "explanation" not in i for i in v["items"])
    with pytest.raises(ValueError):
        eng.submit(v["id"], [{"selected": 0}] * 4)  # 少一題不能交卷
    r = answer_all(eng, v, 0)
    assert all("answer_index" in i and i["explanation"] for i in r["items"])


def test_every_served_question_is_verified_and_has_unique_correct_option(eng):
    from lagen import validate
    from lagen.taxonomy import TAXONOMY
    for _ in range(6):
        v = eng.create_daily(); answer_all(eng, v, 0); eng.advance_day()
    n = 0
    for r in eng.db.execute("select q from items"):
        q = json.loads(r["q"]); n += 1
        assert q["verification_ok"] if "verification_ok" in q else True
        ctx = validate.Ctx(taxonomy=TAXONOMY, learned_sections=set(TAXONOMY.values()), today=0)
        ctx.request = {"concept": q["concept"], "role": q["role"], "difficulty": q["difficulty"]}
        assert validate.validate_candidate({k: v for k, v in q.items() if k not in ("stem", "explanation", "option_texts")}, ctx).status in ("approved",)
    assert n >= 30


def test_wrong_answers_recorded_and_reviews_scheduled_1_3_7(eng):
    v = eng.create_daily(); r = answer_all(eng, v, wrong_positions=[0])
    wrong = [i for i in r["items"] if not i["correct"]]
    assert len(wrong) == 1
    rv = [dict(x) for x in eng.db.execute("select concept, due_day, stage from reviews where done=0 order by due_day")]
    assert [x["due_day"] - 1 for x in rv] == [1, 3, 7] and {x["concept"] for x in rv} == {wrong[0]["concept"]}


def test_next_day_review_item_appears_in_same_role_slot_and_is_marked_done_when_correct(eng):
    v = eng.create_daily(); r = answer_all(eng, v, wrong_positions=[0])
    concept = r["items"][0]["concept"]; role = r["items"][0]["role"]
    d2 = eng.advance_day()
    rev = [i for i in d2["items"] if i["is_review"]]
    assert rev and rev[0]["concept"] == concept and rev[0]["role"] == role
    answer_all(eng, d2, 0)
    assert eng.db.execute("select count(*) c from reviews where done=1 and concept=?", (concept,)).fetchone()["c"] == 1


def test_unfinished_due_reviews_never_marked_done(eng):
    v = eng.create_daily(); answer_all(eng, v, wrong_n=4)  # 4 錯 → 多個到期複習
    eng.advance_day()
    done = eng.db.execute("select count(*) c from reviews where done=1").fetchone()["c"]
    assert done == 0


def test_next_quiz_adjusts_difficulty_by_score(eng):
    v = eng.create_daily(); answer_all(eng, v, 0)                       # 5/5 無不確定 → 難度 +1
    n = eng.create_next()
    assert n["base_difficulty"] == 2 and n["plan"]["adjust_code"] == "PERFECT_UP" and n["level"] == 1  # 正式 Level 不變
    answer_all(eng, n, 0, unsure=True)                                   # 5/5 但有不確定 → 維持 + 1 題進階
    n2 = eng.create_next()
    assert n2["base_difficulty"] == 2 and n2["plan"]["advanced"] == 1
    assert sorted(i["difficulty"] for i in n2["items"]).count(3) >= 1
    answer_all(eng, n2, wrong_n=1)                                       # 4/5 → 維持 + 進階
    n3 = eng.create_next(); assert n3["base_difficulty"] == 2
    answer_all(eng, n3, wrong_n=2)                                       # 3/5 → 維持 + 加強
    n4 = eng.create_next(); assert n4["base_difficulty"] == 2 and n4["plan"]["reinforce"]
    answer_all(eng, n4, wrong_n=4)                                       # 1/5 → 降低 + 基礎優先
    n5 = eng.create_next(); assert n5["base_difficulty"] == 1 and n5["plan"]["foundation"]


def test_only_one_open_extra_quiz_and_daily_idempotent(eng):
    d1 = eng.create_daily(); assert eng.create_daily()["id"] == d1["id"]
    answer_all(eng, d1, 0)
    a = eng.create_next(); b = eng.create_next(); assert a["id"] == b["id"]


def test_resubmit_does_not_double_count(eng):
    v = eng.create_daily(); answer_all(eng, v, wrong_positions=[0]); answer_all(eng, v, wrong_positions=[1])
    assert eng.db.execute("select count(*) c from reviews").fetchone()["c"] == 3


def test_next_day_daily_does_not_overwrite_unfinished_previous(eng):
    d1 = eng.create_daily(); d2 = eng.advance_day()
    assert d1["id"] != d2["id"] and eng.quiz_view(d1["id"])["submitted"] is False


def test_level_follows_daily_only_and_extras_do_not_count(eng):
    for _ in range(3):
        v = eng.create_daily(); answer_all(eng, v, 0)
        for _ in range(2):  # 同一天再做兩份額外測驗,不得累計升級日
            n = eng.create_next(); answer_all(eng, n, 0)
        eng.advance_day()
    assert eng.level_state()[0] == 2                      # 3 個有效日 → L1→L2
    assert eng.create_daily()["level"] == 2


def test_error_type_history_preserved(eng):
    v = eng.create_daily(); r = answer_all(eng, v, wrong_positions=[0])
    for t in ("粗心", "觀念不清", "觀念不清", "計算錯誤"): eng.set_error_type(v["id"], 0, t)
    hist = [dict(x) for x in eng.db.execute("select old_type,new_type from error_history order by id")]
    assert [(h["old_type"], h["new_type"]) for h in hist] == [(None, "粗心"), ("粗心", "觀念不清"), ("觀念不清", "計算錯誤")]
    with pytest.raises(ValueError): eng.set_error_type(v["id"], 1, "粗心")  # 答對的題不能標錯誤類型


def test_angle_rotation_for_same_concept(eng):
    angles = []
    for _ in range(8):
        v = eng.create_daily(); answer_all(eng, v, 0)
        angles += [(i["concept"], i["angle"]) for i in v["items"] if i["concept"] == "linear-independence"]
        eng.advance_day()
    a = [x[1] for x in angles]
    assert len(a) >= 2 and len(set(a)) >= 2


def test_no_unverified_question_ever_served_when_everything_fails(eng, monkeypatch):
    from lagen import validate
    monkeypatch.setattr(validate, "validate_candidate", lambda c, ctx: validate.Result("rejected", [{"stage": "X", "code": "FORCED", "detail": "x"}]))
    v = eng.create_daily()
    assert v["items"] == [] and len(v["plan"]["shortages"]) == 5   # 如實少出並記錄缺口,不補未驗證題


def test_adjust_exhaustive_matches_rules():
    for P in range(1, 5):
        for c in range(6):
            for u in range(c + 1):
                a = adjust(P, c, u); assert 1 <= a["base"] <= 4
    assert adjust(4, 5, 0)["base"] == 4 and adjust(1, 0, 0)["base"] == 1
