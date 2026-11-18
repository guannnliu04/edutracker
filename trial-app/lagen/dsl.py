"""受限的『驗證規格』語言。AI 只能輸出 JSON 規格;我們用 SymPy 自己計算。
絕不 eval / exec AI 產生的任何文字或程式碼。未知運算一律拒絕。"""
from fractions import Fraction
from typing import Any, Callable, Dict

import sympy as sp

from . import fracla

MAX_DIM = 6          # 矩陣大小上限,避免被惡意/失控的規格拖垮
MAX_ENTRY = 10 ** 6  # 係數上限


class SpecError(ValueError):
    """規格本身不合法(未知運算、型別錯誤、超出上限…)。"""


class PreconditionError(ValueError):
    """題目條件不成立(例如要求反矩陣但矩陣奇異、向量維度不一致)。"""


class PartialError(ValueError):
    """超出可完整驗證的範圍(例如特徵值不是有理數)。只能部分驗證 → 不得自動進入正式測驗。"""


def _rat(x: Any) -> sp.Rational:
    if isinstance(x, bool) or isinstance(x, float):
        raise SpecError(f"不接受的數值型別: {type(x).__name__}")
    if isinstance(x, int):
        v = sp.Integer(x)
    elif isinstance(x, str):
        try:
            v = sp.Rational(Fraction(x))
        except (ValueError, ZeroDivisionError):
            raise SpecError(f"不是有理數: {x!r}")
    else:
        raise SpecError(f"不接受的數值型別: {type(x).__name__}")
    if abs(v) > MAX_ENTRY:
        raise SpecError("係數超出上限")
    return v


def _matrix(rows) -> sp.Matrix:
    if not isinstance(rows, list) or not rows or not all(isinstance(r, list) and r for r in rows):
        raise SpecError("matrix 必須是非空的二維陣列")
    if len(rows) > MAX_DIM or len(rows[0]) > MAX_DIM:
        raise SpecError("矩陣超出大小上限")
    if len({len(r) for r in rows}) != 1:
        raise PreconditionError("矩陣各列長度不一致")
    return sp.Matrix([[_rat(x) for x in r] for r in rows])


def _vectors(vs) -> sp.Matrix:
    """向量清單 → 以向量為『行』的矩陣"""
    if not isinstance(vs, list) or not vs:
        raise SpecError("vectors 必須是非空陣列")
    if len({len(v) for v in vs}) != 1:
        raise PreconditionError("向量維度不一致")
    return _matrix([list(v) for v in vs]).T


# ───────── 型別化的值:(type, payload) ─────────
def _f(x) -> Fraction:
    return Fraction(int(x.p), int(x.q))


def v_int(n) -> tuple: return ("int", int(n))
def v_rat(x) -> tuple: return ("rational", _f(sp.Rational(x)))
def v_bool(b) -> tuple: return ("bool", bool(b))
def v_set(xs) -> tuple: return ("set_rational", frozenset(_f(sp.Rational(x)) for x in xs))
def v_mat(m: sp.Matrix) -> tuple: return ("matrix", tuple(tuple(_f(m[i, j]) for j in range(m.cols)) for i in range(m.rows)))
def v_vec(m: sp.Matrix) -> tuple: return ("vector", tuple(_f(x) for x in m))
def v_enum(s: str) -> tuple: return ("enum", s)


def parse_claim(c: Dict[str, Any]) -> tuple:
    """把選項/解析裡的 {"type":..., "value":...} 轉成與運算結果相同的型別化值"""
    if not isinstance(c, dict) or "type" not in c or "value" not in c:
        raise SpecError("claim 必須是 {type, value}")
    t, v = c["type"], c["value"]
    if t == "int":
        if not isinstance(v, int) or isinstance(v, bool): raise SpecError("int claim 必須是整數")
        return ("int", v)
    if t == "rational": return ("rational", Fraction(str(v)))
    if t == "bool":
        if not isinstance(v, bool): raise SpecError("bool claim 必須是布林")
        return ("bool", v)
    if t == "set_rational": return ("set_rational", frozenset(Fraction(str(x)) for x in v))
    if t == "matrix": return ("matrix", tuple(tuple(Fraction(str(x)) for x in r) for r in v))
    if t == "vector": return ("vector", tuple(Fraction(str(x)) for x in v))
    if t == "enum":
        if not isinstance(v, str): raise SpecError("enum claim 必須是字串")
        return ("enum", v)
    raise SpecError(f"未知的 claim 型別: {t}")


# ───────── 運算(白名單) ─────────
def _square(m: sp.Matrix) -> sp.Matrix:
    if m.rows != m.cols: raise PreconditionError("需要方陣")
    return m


def op_rank(a): return v_int(_matrix(a["matrix"]).rank())
def op_nullity(a):
    m = _matrix(a["matrix"]); return v_int(m.cols - m.rank())
def op_det(a): return v_rat(_square(_matrix(a["matrix"])).det())
def op_trace(a): return v_rat(_square(_matrix(a["matrix"])).trace())
def op_rref(a): return v_mat(_matrix(a["matrix"]).rref()[0])
def op_inverse(a):
    m = _square(_matrix(a["matrix"]))
    if m.det() == 0: raise PreconditionError("矩陣奇異,沒有反矩陣")
    return v_mat(m.inv())
def op_independent(a):
    m = _vectors(a["vectors"]); return v_bool(m.rank() == m.cols)
def op_span_dim(a): return v_int(_vectors(a["vectors"]).rank())
def op_rank_of_vectors(a): return v_int(_vectors(a["vectors"]).rank())
def op_is_basis(a):
    m = _vectors(a["vectors"]); n = int(a["ambient_dim"])
    if m.rows != n: raise PreconditionError("向量維度與 ambient_dim 不一致")
    return v_bool(m.cols == n and m.rank() == n)
def op_solution_count(a):
    A = _matrix(a["A"]); b = _matrix([[x] for x in a["b"]]) if isinstance(a["b"], list) else None
    if b is None or b.rows != A.rows: raise PreconditionError("b 與 A 的列數不一致")
    rA, rAb = A.rank(), A.row_join(b).rank()
    return v_enum("none" if rA != rAb else ("unique" if rA == A.cols else "infinite"))
def op_projection(a):
    u, v = _matrix([[x] for x in a["a"]]), _matrix([[x] for x in a["b"]])
    if u.rows != v.rows: raise PreconditionError("向量維度不一致")
    d = (u.T * u)[0]
    if d == 0: raise PreconditionError("投影方向不可為零向量")
    return v_vec(((u.T * v)[0] / d) * u)
def op_pred_ab_zero_nonzero(a):
    A, B = _matrix(a["A"]), _matrix(a["B"])
    if A.cols != B.rows: raise PreconditionError("A、B 無法相乘")
    return v_bool((A * B).is_zero_matrix and not A.is_zero_matrix and not B.is_zero_matrix)
def op_eigenvalues(a):
    m = _square(_matrix(a["matrix"])); ev = m.eigenvals()
    if not all(e.is_rational is True for e in ev):  # 複數或無理特徵值 → 只能部分驗證
        raise PartialError("特徵值不是有理數,只能部分驗證")
    return v_set(ev.keys())
def op_param_dependent(a):
    """向量元素為 [常數, k 的係數];回傳使向量組線性相依的 k(有理數解集合)。向量個數必須等於維度。"""
    k = sp.Symbol("k")
    vs = a["vectors"]
    if len({len(v) for v in vs}) != 1 or len(vs) != len(vs[0]): raise PreconditionError("需要 n 個 n 維向量")
    if len(vs) > 4: raise SpecError("維度超出上限")
    cols = sp.Matrix([[(_rat(c) + _rat(s) * k) for c, s in v] for v in vs]).T
    poly = sp.Poly(sp.expand(cols.det()), k)
    if poly.is_zero: raise PreconditionError("對所有 k 都相依,題目沒有意義")
    roots = sp.roots(poly, filter="R")
    if sum(roots.values()) != poly.degree() or not all(r.is_rational for r in roots): raise PartialError("k 的解不全是有理數")
    return v_set(roots.keys())


def op_independence_report(a):
    m = _vectors(a["vectors"]); r = m.rank()
    return v_enum(f"{'indep' if r == m.cols else 'dep'}_rank{r}")


def resolve(obj: Any, objects: Dict[str, Any]) -> Any:
    """把 {"ref": 名稱, "t": 是否轉置} 換成實際物件資料。題目文字與驗證規格因此來自『同一份資料』,不可能對不上。"""
    if isinstance(obj, dict):
        if set(obj) <= {"ref", "t"} and "ref" in obj:
            name = obj["ref"]
            if name not in objects: raise SpecError(f"參照不存在的物件: {name}")
            data = objects[name]["data"]
            if obj.get("t"):
                if objects[name]["kind"] != "matrix": raise SpecError("只有 matrix 可以轉置")
                data = [list(r) for r in zip(*data)]
            return data
        return {k: resolve(v, objects) for k, v in obj.items()}
    if isinstance(obj, list): return [resolve(x, objects) for x in obj]
    return obj


OPS: Dict[str, Callable] = {
    "independence_report": op_independence_report,
    "rank": op_rank, "nullity": op_nullity, "det": op_det, "trace": op_trace, "rref": op_rref,
    "inverse": op_inverse, "independent": op_independent, "span_dim": op_span_dim, "is_basis": op_is_basis,
    "solution_count": op_solution_count, "projection": op_projection, "eigenvalues": op_eigenvalues,
    "param_dependent": op_param_dependent, "pred_ab_zero_nonzero": op_pred_ab_zero_nonzero,
}


def evaluate(spec: Any) -> tuple:
    """執行驗證規格。只接受 {"op": 白名單名稱, "args": {…}}"""
    if not isinstance(spec, dict) or set(spec) - {"op", "args"}:
        raise SpecError("規格只允許 op 與 args 兩個欄位")
    op = spec.get("op")
    if not isinstance(op, str) or op not in OPS:
        raise SpecError(f"未知或不允許的運算: {str(op)[:40]!r}")
    args = spec.get("args")
    if not isinstance(args, dict): raise SpecError("args 必須是物件")
    try:
        return OPS[op](args)
    except KeyError as e:
        raise SpecError(f"缺少參數: {e}")


# ───────── 第二套獨立實作的交叉驗證 ─────────
def crosscheck(spec: Dict[str, Any]) -> tuple:
    """回傳 ('agree'|'mismatch'|'none', 說明)。只有部分運算有第二套實作。"""
    op, a = spec["op"], spec["args"]
    try:
        if op in ("rank", "nullity", "det", "rref", "inverse", "trace"):
            m = fracla.to_mat(a["matrix"])
            if op == "rank": other = ("int", fracla.rank(m))
            elif op == "nullity": other = ("int", len(m[0]) - fracla.rank(m))
            elif op == "det": other = ("rational", fracla.det(m))
            elif op == "trace": other = ("rational", sum(m[i][i] for i in range(len(m))))
            elif op == "rref": other = ("matrix", tuple(tuple(r) for r in fracla.rref(m)[0]))
            else:
                inv = fracla.inverse(m); other = ("matrix", tuple(tuple(r) for r in inv))
        elif op in ("independent", "span_dim", "is_basis"):
            cols = fracla.to_mat(a["vectors"])  # 每個向量一列 → rank 相同
            r = fracla.rank(cols)
            if op == "independent": other = ("bool", r == len(cols))
            elif op == "span_dim": other = ("int", r)
            else: other = ("bool", len(cols) == int(a["ambient_dim"]) == len(cols[0]) and r == len(cols))
        elif op == "solution_count":
            A = fracla.to_mat(a["A"]); aug = [r + [Fraction(x)] for r, x in zip(A, a["b"])]
            rA, rAb = fracla.rank(A), fracla.rank(aug)
            other = ("enum", "none" if rA != rAb else ("unique" if rA == len(A[0]) else "infinite"))
        elif op == "pred_ab_zero_nonzero":
            A, B = fracla.to_mat(a["A"]), fracla.to_mat(a["B"])
            prod = fracla.matmul(A, B)
            other = ("bool", all(x == 0 for r in prod for x in r) and any(x != 0 for r in A for x in r) and any(x != 0 for r in B for x in r))
        else:
            return "none", "此運算沒有第二套實作"
    except (ZeroDivisionError, TypeError, TypeError):
        return "mismatch", "第二套實作計算失敗"
    mine = evaluate(spec)
    return ("agree", "") if mine == other else ("mismatch", f"SymPy={mine} 第二套={other}")
