"""題目與選項的文字,一律由『結構化物件 / claim』在伺服器端渲染。AI 只提供敘述文字與結構。"""
import re
from fractions import Fraction

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
RAW_MATRIX = re.compile(r"\\begin\{[bp]?matrix\}|\\\[|\$\$")

ENUM_TEXT = {
    "indep_rank3": "線性獨立,秩為 3", "dep_rank2": "線性相依,秩為 2", "dep_rank1": "線性相依,秩為 1", "dep_rank0": "線性相依,秩為 0",
    "indep_rank2": "線性獨立,秩為 2", "indep_rank1": "線性獨立,秩為 1", "indep_rank4": "線性獨立,秩為 4", "dep_rank3": "線性相依,秩為 3",
    "none": "無解", "unique": "恰有一組解", "infinite": "有無限多組解",
}


def fmt(x) -> str:
    if isinstance(x, float): raise TypeError("浮點數不得進入題目文字(會產生 13333333333333333/10000... 這種怪分數);請用 Fraction 或整數")
    f = Fraction(str(x))
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def latex_matrix(rows) -> str:
    return "$\\begin{bmatrix}" + "\\\\".join("&".join(fmt(x) for x in r) for r in rows) + "\\end{bmatrix}$"


def _col(v) -> str:
    return "\\begin{bmatrix}" + "\\\\".join(fmt(x) for x in v) + "\\end{bmatrix}"


def render_object(o) -> str:
    k, d = o["kind"], o["data"]
    if k == "matrix": return latex_matrix(d)
    if k == "vector": return "$" + _col(d) + "$"
    if k == "vectors": return "$" + ",\\ ".join(_col(v) for v in d) + "$"
    if k == "param_vectors":
        def e(c, s):
            c, s = Fraction(str(c)), Fraction(str(s))
            parts = ([fmt(c)] if c != 0 else []) + ([("" if s == 1 else "-" if s == -1 else fmt(s)) + "k"] if s != 0 else [])
            return "+".join(parts).replace("+-", "-") or "0"
        return "$" + ",\\ ".join("\\begin{bmatrix}" + "\\\\".join(e(c, s) for c, s in v) + "\\end{bmatrix}" for v in d) + "$"
    raise ValueError(f"未知物件種類: {k}")


def render_template(tpl: str, objects) -> str:
    def sub(m):
        name = m.group(1)
        if name not in objects: raise KeyError(name)
        return render_object(objects[name])
    return PLACEHOLDER.sub(sub, tpl)


def render_claim(c) -> str:
    t, v = c["type"], c["value"]
    if t in ("int", "rational"): return fmt(v)
    if t == "bool": return "是" if v else "否"
    if t == "set_rational": return "$\\{" + ",\\ ".join(sorted({fmt(x) for x in v}, key=lambda s: Fraction(s))) + "\\}$"   # 集合要去重後渲染,相等的集合文字必須相同
    if t == "matrix": return latex_matrix(v)
    if t == "vector": return "$" + _col(v) + "$"
    if t == "enum": return ENUM_TEXT.get(v, v)
    raise ValueError(t)
