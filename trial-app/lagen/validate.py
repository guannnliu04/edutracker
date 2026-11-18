"""AI / 模板 / 題庫候選題的驗證流程。任何一關失敗就不得進入正式測驗。
狀態:approved(完整驗證通過)、rejected(確定有問題)、needs_review(無法完整自動驗證 → 不得自動進入正式測驗)。
注意:『第二個 AI 模型認為正確』完全不是驗證依據,本流程沒有任何讀取它的地方。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from . import dedup, dsl
from .render import PLACEHOLDER, RAW_MATRIX, render_claim, render_object, render_template

ROLES = {"basic", "progress", "bank"}
SOURCES = {"bank_verified", "param_variant", "ai_generated"}
ANGLES = {"definition", "property_judgement", "true_false", "counterexample", "computation", "condition_change", "integration", "exam_adapt", "rref", "rank", "nullity"}
VERIFY_MODES = {"value", "predicate", "none"}


@dataclass
class Ctx:
    taxonomy: Dict[str, str]                 # 觀念 → 小節
    learned_sections: Set[str]               # 已學小節
    request: Dict[str, Any] = field(default_factory=dict)   # 這一格要的:role、difficulty、concept、allowed_angles
    recent: List[Dict[str, Any]] = field(default_factory=list)
    today: int = 0
    second_model_agrees: bool = False        # 刻意放著:驗證流程不會讀它(見測試)
    dedup_cfg: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    status: str
    failures: List[Dict[str, str]] = field(default_factory=list)
    verification_level: str = "none"          # full | partial | none
    crosscheck: str = "none"
    fingerprints: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return self.status == "approved"


def _fail(stage: str, code: str, detail: str, status: str = "rejected", level: str = "none") -> Result:
    return Result(status=status, failures=[{"stage": stage, "code": code, "detail": detail}], verification_level=level)


def _schema(c: Dict[str, Any]) -> Optional[Result]:
    need = ["concept", "section", "role", "source", "difficulty", "angle", "stem_template", "verify_mode", "options", "answer_index", "explanation_template"]
    miss = [k for k in need if k not in c]
    if miss: return _fail("S1_schema", "MISSING_FIELDS", ",".join(miss))
    if c["role"] not in ROLES: return _fail("S1_schema", "BAD_ROLE", str(c["role"]))
    if c["source"] not in SOURCES: return _fail("S1_schema", "BAD_SOURCE", str(c["source"]))
    if c["angle"] not in ANGLES: return _fail("S1_schema", "BAD_ANGLE", str(c["angle"]))
    if c["verify_mode"] not in VERIFY_MODES: return _fail("S1_schema", "BAD_VERIFY_MODE", str(c["verify_mode"]))
    if not (isinstance(c["difficulty"], int) and not isinstance(c["difficulty"], bool) and 1 <= c["difficulty"] <= 4): return _fail("S1_schema", "BAD_DIFFICULTY", str(c["difficulty"]))
    if not isinstance(c["options"], list) or len(c["options"]) != 4: return _fail("S1_schema", "NOT_FOUR_OPTIONS", f"選項數={len(c['options']) if isinstance(c['options'], list) else '?'}")
    if not (isinstance(c["answer_index"], int) and not isinstance(c["answer_index"], bool) and 0 <= c["answer_index"] <= 3): return _fail("S1_schema", "BAD_ANSWER_INDEX", str(c["answer_index"]))
    for k in ("stem_template", "explanation_template"):
        if not isinstance(c[k], str) or len(c[k].strip()) < 8: return _fail("S1_schema", "EMPTY_TEXT", k)
    objs = c.get("objects", {})
    if not isinstance(objs, dict): return _fail("S1_schema", "BAD_OBJECTS", "objects 必須是物件")
    # 題面不可自帶矩陣文字:數字必須經由 {{物件}} 由伺服器渲染,才保證題面與驗證規格是同一份資料
    for k in ("stem_template", "explanation_template"):
        if RAW_MATRIX.search(c[k]): return _fail("S1_schema", "RAW_MATRIX_IN_TEXT", f"{k} 含手寫矩陣,請改用 {{{{物件}}}} 佔位符")
    used = set(PLACEHOLDER.findall(c["stem_template"]))
    if used - set(objs): return _fail("S1_schema", "UNKNOWN_PLACEHOLDER", ",".join(sorted(used - set(objs))))
    if c["verify_mode"] != "none" and set(objs) - used - set(PLACEHOLDER.findall(c["explanation_template"])) and c["verify_mode"] == "value":
        return _fail("S1_schema", "UNUSED_OBJECT", ",".join(sorted(set(objs) - used)))
    return None


def _value_checks(c: Dict[str, Any]):
    """回傳 (None, level, crosscheck) 或 (Result, ...)"""
    objs = c.get("objects", {})
    spec = dsl.resolve(c["verifier"], objs)
    truth = dsl.evaluate(spec)
    claims = [dsl.parse_claim(o["claim"]) for o in c["options"]]
    if any(cl[0] != truth[0] for cl in claims): return _fail("S3_recompute", "CLAIM_TYPE_MISMATCH", f"選項型別與運算結果型別({truth[0]})不一致"), "full", "none"
    texts = [render_claim(o["claim"]) for o in c["options"]]
    if len(set(texts)) != 4: return _fail("S1_schema", "DUPLICATE_OPTION_TEXT", "有兩個選項渲染後文字相同"), "full", "none"
    hits = [i for i, cl in enumerate(claims) if cl == truth]
    if not hits: return _fail("S3_recompute", "NO_CORRECT_OPTION", "沒有任何選項等於驗算結果"), "full", "none"
    if len(hits) > 1: return _fail("S3_recompute", "MULTIPLE_CORRECT_OPTIONS", f"選項 {hits} 都等於驗算結果"), "full", "none"
    if hits[0] != c["answer_index"]: return _fail("S3_recompute", "ANSWER_KEY_MISMATCH", f"標示答案是 {c['answer_index']},驗算結果對應 {hits[0]}"), "full", "none"
    x, why = dsl.crosscheck(spec)
    if x == "mismatch": return _fail("S3_recompute", "CROSSCHECK_MISMATCH", why), "full", x
    # 解析結論必須等於驗算結果
    if "explanation_claim" not in c: return _fail("S4_explanation", "NO_EXPLANATION_CLAIM", "缺少 explanation_claim"), "full", x
    if dsl.parse_claim(c["explanation_claim"]) != truth: return _fail("S4_explanation", "EXPLANATION_MISMATCH", "解析的結論與驗算結果不一致"), "full", x
    return None, "full", x


def _predicate_checks(c: Dict[str, Any]):
    objs = c.get("objects", {})
    flags, xs = [], []
    for o in c["options"]:
        if "verifier" not in o: return _fail("S1_schema", "MISSING_OPTION_VERIFIER", "predicate 模式每個選項都需要 verifier"), "full", "none"
        spec = dsl.resolve(o["verifier"], {**objs, **o.get("objects", {})})
        r = dsl.evaluate(spec)
        if r[0] != "bool": return _fail("S3_recompute", "PREDICATE_NOT_BOOL", "predicate 運算必須回傳布林"), "full", "none"
        flags.append(r[1]); xs.append(dsl.crosscheck(spec))
    if any(x[0] == "mismatch" for x in xs): return _fail("S3_recompute", "CROSSCHECK_MISMATCH", "; ".join(x[1] for x in xs if x[0] == "mismatch")), "full", "mismatch"
    cx = "agree" if all(x[0] == "agree" for x in xs) else "none"
    trues = [i for i, f in enumerate(flags) if f]
    if not trues: return _fail("S3_recompute", "NO_CORRECT_OPTION", "沒有選項滿足條件"), "full", cx
    if len(trues) > 1: return _fail("S3_recompute", "MULTIPLE_CORRECT_OPTIONS", f"選項 {trues} 都滿足條件"), "full", cx
    if trues[0] != c["answer_index"]: return _fail("S3_recompute", "ANSWER_KEY_MISMATCH", f"標示答案是 {c['answer_index']},實際滿足條件的是 {trues[0]}"), "full", cx
    if c.get("explanation_answer_index") != trues[0]: return _fail("S4_explanation", "EXPLANATION_MISMATCH", "解析指向的選項與驗算結果不一致"), "full", cx
    return None, "full", cx


def _derived_checks(c: Dict[str, Any]) -> Optional[Result]:
    """物件若宣告 derived(例如解析中顯示的 RREF),必須等於伺服器重新計算的結果"""
    objs = c.get("objects", {})
    for name, o in objs.items():
        if "derived" in o:
            want = dsl.evaluate(dsl.resolve(o["derived"], objs))
            got = dsl.parse_claim({"type": "matrix", "value": o["data"]}) if want[0] == "matrix" else None
            if got != want:
                return _fail("S4_explanation", "DERIVED_OBJECT_MISMATCH", f"物件 {name} 與重新計算的結果不一致")
    return None


def validate_candidate(c: Dict[str, Any], ctx: Ctx) -> Result:
    # S1 結構與完整性
    try:
        bad = _schema(c)
    except Exception as e:  # noqa: BLE001 — 驗證器自身出錯也一律視為失敗,絕不讓流程崩潰
        return _fail("S1_schema", "VALIDATOR_CRASH", f"{type(e).__name__}: {e}")
    if bad: return bad
    # S7(提前):無法自動驗證的題型 → 不得自動進入正式測驗
    if c["verify_mode"] == "none":
        return _fail("S3_recompute", "UNVERIFIABLE_TYPE", "此題型(例如證明題)無法程式驗證,需人工審核", status="needs_review")
    # S2 條件一致、S3 獨立驗算、S4 解析一致
    try:
        res, level, cx = _value_checks(c) if c["verify_mode"] == "value" else _predicate_checks(c)
    except dsl.PreconditionError as e:
        return _fail("S2_preconditions", "PRECONDITION", str(e))
    except dsl.PartialError as e:
        return _fail("S3_recompute", "PARTIAL_ONLY", str(e), status="needs_review", level="partial")
    except dsl.SpecError as e:
        return _fail("S1_schema", "BAD_SPEC", str(e))
    except Exception as e:  # noqa: BLE001
        return _fail("S3_recompute", "VERIFIER_CRASH", f"{type(e).__name__}: {e}")
    if res: return res
    try:
        dres = _derived_checks(c)
    except Exception as e:  # noqa: BLE001
        return _fail("S4_explanation", "VERIFIER_CRASH", f"{type(e).__name__}: {e}")
    if dres: return dres
    # S5 範圍:觀念、小節、難度、角色、已學範圍
    if c["concept"] not in ctx.taxonomy: return _fail("S5_scope", "UNKNOWN_CONCEPT", c["concept"], level=level)
    if ctx.taxonomy[c["concept"]] != c["section"]: return _fail("S5_scope", "SECTION_MISMATCH", f"{c['concept']} 屬於 {ctx.taxonomy[c['concept']]},題目卻標 {c['section']}", level=level)
    if c["section"] not in ctx.learned_sections: return _fail("S5_scope", "NOT_LEARNED_YET", f"小節 {c['section']} 尚未學過", level=level)
    rq = ctx.request
    for key, code in (("difficulty", "DIFFICULTY_MISMATCH"), ("role", "ROLE_MISMATCH"), ("concept", "CONCEPT_MISMATCH")):
        if key in rq and rq[key] != c[key]: return _fail("S5_scope", code, f"要求 {rq[key]},題目是 {c[key]}", level=level)
    if "allowed_angles" in rq and c["angle"] not in rq["allowed_angles"]: return _fail("S5_scope", "ANGLE_NOT_ALLOWED", c["angle"], level=level)
    # S6 去重
    fp = dedup.fingerprints(c)
    # 參數化變式題只換數字、題面本來就一樣:題面相似不算重複(數學內容相同仍會被擋)。近似重複檢查只用在 AI 手寫文字題(試用版發現:不豁免會讓模板題 7 天內全被擋、出不出題)
    dcfg = {**ctx.dedup_cfg, "skip_near": c.get("source") == "param_variant"}
    d = dedup.check_duplicate(fp, ctx.recent, ctx.today, dcfg, bool(ctx.request.get("review_variant")))
    if d: return Result("rejected", [{"stage": "S6_dedup", "code": d[0], "detail": d[1]}], level, cx, fp)
    return Result("approved", [], level, cx, fp)


def finalize(c: Dict[str, Any]) -> Dict[str, Any]:
    """通過驗證後,由伺服器渲染出最終題面、選項與解析文字(AI 手寫的數字不會進到使用者面前)"""
    objs = c.get("objects", {})
    out = dict(c)
    out["stem"] = render_template(c["stem_template"], objs)
    out["explanation"] = render_template(c["explanation_template"], objs)
    if c["verify_mode"] == "value":
        out["option_texts"] = [render_claim(o["claim"]) for o in c["options"]]
    else:
        out["option_texts"] = ["; ".join(f"{k}={render_object(v)}" for k, v in sorted(o.get("objects", {}).items())) for o in c["options"]]
    return out
