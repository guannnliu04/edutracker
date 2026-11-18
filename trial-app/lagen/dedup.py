"""去重:三種訊號。同一觀念可以反覆練習,但不應一直出現幾乎相同的題。
1) 數學內容簽章(param_sig):解析後的驗證參數(實際的矩陣、向量數字)完全相同 → 數學上是同一題,即使換了敘述。
2) 結構簽章(struct_sig)+ 遮蔽數字後的文字相似度:同觀念、同出題角度、同運算、題面幾乎一樣 → 太像。
3) 內容雜湊(content_hash):整題完全相同。"""
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from . import dsl
from .render import PLACEHOLDER


def _h(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _resolved(spec, objects):
    return dsl.resolve(spec, objects)


def param_signature(c: Dict[str, Any]) -> str:
    objs = c.get("objects", {})
    if c["verify_mode"] == "value":
        return _h(["v", _resolved(c["verifier"], objs), c.get("stem_template", "")[:0]])
    parts = sorted(_h(_resolved(o["verifier"], {**objs, **o.get("objects", {})})) for o in c["options"])
    return _h(["p", parts])


def struct_signature(c: Dict[str, Any]) -> str:
    op = c["verifier"]["op"] if c["verify_mode"] == "value" else "pred:" + c["options"][0]["verifier"]["op"]
    shape = ""
    objs = c.get("objects", {})
    for name in sorted(objs):
        d = objs[name]["data"]
        shape += f"{name}:{len(d)}x{len(d[0]) if d and isinstance(d[0], list) else 1};"
    return "|".join([c["concept"], c["angle"], op, str(c["difficulty"]), shape])


def normalize_text(t: str) -> str:
    t = PLACEHOLDER.sub("<obj>", t)
    t = re.sub(r"\d+", "#", t)
    return re.sub(r"\s+", "", t.lower())


def ngrams(s: str, n: int = 3) -> set:
    return {s[i:i + n] for i in range(max(1, len(s) - n + 1))}


def jaccard(a: str, b: str) -> float:
    A, B = ngrams(a), ngrams(b)
    return len(A & B) / len(A | B) if A | B else 1.0


def fingerprints(c: Dict[str, Any]) -> Dict[str, Any]:
    opts = [json.dumps([o.get("claim"), o.get("objects"), o.get("verifier")], sort_keys=True, default=str) for o in c["options"]]  # 預測式題型的選項內容在 objects/verifier,不能只看 claim(試用版發現的真實漏洞)
    return {
        "content_hash": _h([normalize_text(c["stem_template"]), c.get("objects"), opts]),
        "param_sig": param_signature(c),
        "struct_sig": struct_signature(c),
        "norm_text": normalize_text(c["stem_template"]),
    }


DEFAULTS = {"param_days": 60, "near_days": 7, "near_threshold": 0.85}


def check_duplicate(fp: Dict[str, Any], recent: List[Dict[str, Any]], today: int, cfg: Optional[dict] = None, review_variant: bool = False) -> Optional[Tuple[str, str]]:
    cfg = {**DEFAULTS, **(cfg or {})}
    for r in recent:
        age = today - r["day"]
        if r["content_hash"] == fp["content_hash"]:
            return "DUP_CONTENT", f"與 {age} 天前的題目完全相同"
        if age <= cfg["param_days"] and r["param_sig"] == fp["param_sig"]:
            return "DUP_PARAMS", f"與 {age} 天前的題目數學內容相同(僅敘述不同)"
        # 複習變式(同觀念、換數字)是被允許的,所以只擋「數學內容相同」,不擋「題面相似」
        if not review_variant and not cfg.get("skip_near") and age <= cfg["near_days"] and r["struct_sig"] == fp["struct_sig"] and jaccard(r["norm_text"], fp["norm_text"]) >= cfg["near_threshold"]:
            return "DUP_NEAR", f"與 {age} 天前的題目結構與題面幾乎相同(相似度 {jaccard(r['norm_text'], fp['norm_text']):.2f})"
    return None
