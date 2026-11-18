"""參數化題目模板:每個模板都必須『重新計算』答案與解析,不是只換數字。
模板產出的題目走和 AI 候選題完全相同的驗證流程。"""
import random
from fractions import Fraction
from typing import Any, Dict, List

from . import dsl, fracla
from .render import fmt


# ───────── 小工具 ─────────
def _claim(t, v): return {"type": t, "value": v}
def c_int(n): return _claim("int", int(n))
def c_rat(x): return _claim("rational", fmt(x))
def c_set(xs): return _claim("set_rational", sorted({fmt(x) for x in xs}, key=lambda s: Fraction(s)))
def c_mat(rows): return _claim("matrix", [[fmt(x) for x in r] for r in rows])
def c_vec(v): return _claim("vector", [fmt(x) for x in v])
def c_enum(s): return _claim("enum", s)
def obj_matrix(rows, **extra): return {"kind": "matrix", "data": [[int(x) if Fraction(x).denominator == 1 else fmt(x) for x in r] for r in rows], **extra}
def obj_vectors(vs): return {"kind": "vectors", "data": [list(map(int, v)) for v in vs]}


def rand_matrix(rng, m, n, lo, hi): return [[rng.randint(lo, hi) for _ in range(n)] for _ in range(m)]


def matmul(a, b): return [[sum(x * y for x, y in zip(r, c)) for c in zip(*b)] for r in a]


def mat_with_rank(rng, m, n, r, lo, hi):
    for _ in range(200):
        B, C = rand_matrix(rng, m, r, lo, hi), rand_matrix(rng, r, n, lo, hi)
        A = matmul(B, C)
        if fracla.rank(fracla.to_mat(A)) == r: return A
    raise RuntimeError("無法建構指定秩的矩陣")


def _options(rng, truth: dict, distractors: List[dict], fallback: List[dict] = ()):
    T = dsl.parse_claim(truth); seen = {T}; pool = []
    for group in (distractors, fallback):  # 先用「常見錯誤」型的干擾選項,不足才用備用的
        g = []
        for d in group:
            k = dsl.parse_claim(d)
            if k not in seen: seen.add(k); g.append(d)
        rng.shuffle(g)
        pool += g
        if len(pool) >= 3: break
    if len(pool) < 3: raise RuntimeError("干擾選項不足")
    opts = [truth] + pool[:3]
    rng.shuffle(opts)
    return [{"claim": o} for o in opts], opts.index(truth)


def _base(concept, role, difficulty, angle, template_id, source="param_variant"):
    return {"concept": concept, "section": None, "role": role, "source": source, "difficulty": difficulty, "angle": angle, "template_id": template_id}


def _fill_section(c):
    from .taxonomy import TAXONOMY
    c["section"] = TAXONOMY[c["concept"]]
    return c


def _rref_obj(A_name="A"):
    return {"op": "rref", "args": {"matrix": {"ref": A_name}}}


# ───────── 模板 ─────────
def rank_computation(rng, difficulty, role):
    m, n, rs = {1: (3, 3, [2]), 2: (3, 4, [2, 3]), 3: (4, 4, [2, 3]), 4: (4, 5, [3])}[difficulty]
    lo, hi = (-2, 2) if difficulty == 1 else (-3, 3)
    r = rng.choice(rs); A = mat_with_rank(rng, m, n, r, lo, hi)
    R = [list(map(fmt, row)) for row in fracla.rref(fracla.to_mat(A))[0]]
    nonzero_rows = sum(any(x != 0 for x in row) for row in A)
    c = _base("rank", role, difficulty, "rank", "rank_computation")
    c.update(objects={"A": obj_matrix(A), "R": obj_matrix(R, derived=_rref_obj())}, stem_template="設矩陣 {{A}},求 $\\operatorname{rank}(A)$。",
             verify_mode="value", verifier={"op": "rank", "args": {"matrix": {"ref": "A"}}},
             explanation_template=f"以列運算將 $A$ 化為 RREF:{{{{R}}}},共有 {r} 個主元,因此 $\\operatorname{{rank}}(A)={r}$。", explanation_claim=c_int(r))
    c["options"], c["answer_index"] = _options(rng, c_int(r), [c_int(n - r), c_int(min(m, n)), c_int(nonzero_rows), c_int(r + 1), c_int(max(r - 1, 0)), c_int(m)], [c_int(i) for i in range(0, 8)])
    return _fill_section(c)


def nullity_computation(rng, difficulty, role):
    m, n, rs = {1: (3, 4, [2]), 2: (3, 4, [2, 3]), 3: (4, 5, [2, 3]), 4: (4, 6, [3, 4])}[difficulty]
    r = rng.choice(rs); A = mat_with_rank(rng, m, n, r, -3, 3)
    R = [list(map(fmt, row)) for row in fracla.rref(fracla.to_mat(A))[0]]
    z = n - r
    c = _base("nullity", role, difficulty, "nullity", "nullity_computation")
    c.update(objects={"A": obj_matrix(A), "R": obj_matrix(R, derived=_rref_obj())}, stem_template="設矩陣 {{A}},求零空間 $\\ker(A)$ 的維度。",
             verify_mode="value", verifier={"op": "nullity", "args": {"matrix": {"ref": "A"}}},
             explanation_template=f"RREF 為 {{{{R}}}},主元欄 {r} 個、共 {n} 欄,自由變數有 {n}-{r}={z} 個,所以 $\\dim\\ker(A)={z}$。", explanation_claim=c_int(z))
    c["options"], c["answer_index"] = _options(rng, c_int(z), [c_int(r), c_int(m - r), c_int(z + 1), c_int(max(z - 1, 0)), c_int(n)], [c_int(i) for i in range(0, 8)])
    return _fill_section(c)


def det3(rng, difficulty, role):
    lo, hi = (0, 2) if difficulty == 1 else (-3, 3)
    for _ in range(200):
        A = rand_matrix(rng, 3, 3, lo, hi); d = fracla.det(fracla.to_mat(A))
        if d != 0: break
    diag = A[0][0] * A[1][1] * A[2][2]
    c = _base("determinant", role, difficulty, "computation", "det3")
    c.update(objects={"A": obj_matrix(A)}, stem_template="求 {{A}} 的行列式 $\\det(A)$。", verify_mode="value", verifier={"op": "det", "args": {"matrix": {"ref": "A"}}},
             explanation_template=f"依第一列餘因子展開(或以列運算化為上三角矩陣)可得 $\\det(A)={fmt(d)}$。", explanation_claim=c_rat(d))
    c["options"], c["answer_index"] = _options(rng, c_rat(d), [c_rat(-d), c_rat(diag), c_rat(d + 1), c_rat(d - 1), c_rat(d + 2), c_rat(2 * d)])
    return _fill_section(c)


def _indep_options(rng, truth):
    return _options(rng, c_enum(truth), [c_enum(x) for x in ("indep_rank3", "dep_rank2", "dep_rank1", "dep_rank0")])


def independence_definition(rng, difficulty, role):
    dep = rng.random() < 0.5
    for _ in range(200):
        v1, v2 = rand_matrix(rng, 2, 3, -2, 2)
        if fracla.rank(fracla.to_mat([v1, v2])) == 2: break
    if dep:
        a, b = rng.choice([1, 2, -1]), rng.choice([1, -1, 2]); v3 = [a * x + b * y for x, y in zip(v1, v2)]
    else:
        while True:
            v3 = [rng.randint(-2, 2) for _ in range(3)]
            if fracla.rank(fracla.to_mat([v1, v2, v3])) == 3: break
    r = fracla.rank(fracla.to_mat([v1, v2, v3])); truth = f"{'indep' if r == 3 else 'dep'}_rank{r}"
    c = _base("linear-independence", role, difficulty, "definition", "independence_definition")
    c.update(objects={"V": obj_vectors([v1, v2, v3])}, stem_template="判斷向量組 {{V}} 是否線性獨立(是否只有零係數能使線性組合為零向量),並求其秩。",
             verify_mode="value", verifier={"op": "independence_report", "args": {"vectors": {"ref": "V"}}},
             explanation_template="線性獨立等價於「$c_1v_1+c_2v_2+c_3v_3=0$ 只有零解」,也就是由這些向量為行所組成矩陣的秩等於向量個數;秩即為此向量組張成空間的維度。", explanation_claim=c_enum(truth))
    c["options"], c["answer_index"] = _indep_options(rng, truth)
    return _fill_section(c)


def independence_rref(rng, difficulty, role):
    r = rng.choice([2, 3]); A = mat_with_rank(rng, 3, 3, r, -2, 2)
    R = [list(map(fmt, row)) for row in fracla.rref(fracla.to_mat(A))[0]]
    truth = f"{'indep' if r == 3 else 'dep'}_rank{r}"
    c = _base("linear-independence", role, difficulty, "rref", "independence_rref")
    c.update(objects={"A": obj_matrix(A), "R": obj_matrix(R, derived=_rref_obj())}, stem_template="矩陣 {{A}} 的 RREF 為 {{R}}。關於 $A$ 的三個行向量,下列何者正確?",
             verify_mode="value", verifier={"op": "independence_report", "args": {"vectors": {"ref": "A", "t": True}}},
             explanation_template="RREF 的主元欄數就是 $\\operatorname{rank}(A)$;行向量線性獨立,若且唯若主元欄數等於欄數。", explanation_claim=c_enum(truth))
    c["options"], c["answer_index"] = _indep_options(rng, truth)
    return _fill_section(c)


def independence_param(rng, difficulty, role):
    for _ in range(500):
        vs = [[[rng.randint(-2, 2), rng.randint(-1, 1)] for _ in range(3)] for _ in range(3)]
        spec = {"op": "param_dependent", "args": {"vectors": vs}}
        try:
            truth = dsl.evaluate(spec)
        except (dsl.PreconditionError, dsl.PartialError):
            continue
        if truth[1]: break
    roots = sorted(truth[1])
    cs = c_set(roots)
    dist = [c_set([-x for x in roots]), c_set(roots + [max(roots) + 1]), c_set([roots[0] + 1]), c_set([0]), c_set([x + 1 for x in roots])] + ([c_set(roots[:-1])] if len(roots) > 1 else [])
    c = _base("linear-independence", role, difficulty, "condition_change", "independence_param")
    c.update(objects={"V": {"kind": "param_vectors", "data": vs}}, stem_template="設向量組 {{V}}。求所有使這組向量線性相依的實數 $k$。",
             verify_mode="value", verifier=spec, explanation_template="線性相依等價於以這些向量為行的 $3\\times 3$ 矩陣行列式為 0。解行列式為 $k$ 的多項式方程式即得答案。", explanation_claim=cs)
    c["options"], c["answer_index"] = _options(rng, cs, dist, [c_set([x + 2 for x in roots]), c_set([roots[0] - 1]), c_set([2]), c_set([-1]), c_set([roots[0] + 3])])
    return _fill_section(c)


def counterexample_product_zero(rng, difficulty, role):
    def rank1(u, v): return [[a * b for b in v] for a in u]
    while True:
        u, v, w, z = ([rng.randint(-2, 2) for _ in range(2)] for _ in range(4))
        if any(u) and any(v) and any(w) and any(z) and u[0] * 0 == 0 and sum(x * y for x, y in zip(v, w)) == 0: break
    A, B = rank1(u, v), rank1(w, z)
    def rnd_nonzero():
        while True:
            M = rand_matrix(rng, 2, 2, -2, 2)
            if any(x for r in M for x in r): return M
    pairs = [(A, B)]
    while len(pairs) < 2:
        X, Y = rnd_nonzero(), rnd_nonzero()
        if any(x for r in matmul(X, Y) for x in r): pairs.append((X, Y))
    pairs.append(([[0, 0], [0, 0]], rnd_nonzero())); pairs.append((rnd_nonzero(), [[0, 0], [0, 0]]))
    order = list(range(4)); rng.shuffle(order)
    options = [{"objects": {"A": obj_matrix(pairs[i][0]), "B": obj_matrix(pairs[i][1])}, "verifier": {"op": "pred_ab_zero_nonzero", "args": {"A": {"ref": "A"}, "B": {"ref": "B"}}}} for i in order]
    ans = order.index(0)
    c = _base("matrix-properties", role, difficulty, "counterexample", "counterexample_product_zero")
    c.update(objects={}, stem_template="命題:「若 $AB=0$,則 $A=0$ 或 $B=0$。」下列哪一組 $(A,B)$ 是這個命題的反例?", verify_mode="predicate", options=options, answer_index=ans,
             explanation_template="反例必須同時滿足 $AB=0$、$A\\neq 0$ 且 $B\\neq 0$。只有一個選項三個條件同時成立,其餘不是 $AB\\neq 0$,就是其中一個矩陣為零矩陣。", explanation_answer_index=ans)
    return _fill_section(c)


def basis_selection(rng, difficulty, role):
    def indep3():
        while True:
            vs = rand_matrix(rng, 3, 3, -2, 2)
            if fracla.rank(fracla.to_mat(vs)) == 3: return vs
    good = indep3()
    dep3 = rand_matrix(rng, 2, 3, -2, 2)
    while fracla.rank(fracla.to_mat(dep3)) != 2: dep3 = rand_matrix(rng, 2, 3, -2, 2)
    dep3 = dep3 + [[x + y for x, y in zip(dep3[0], dep3[1])]]
    two = indep3()[:2]
    four = indep3() + [rand_matrix(rng, 1, 3, -2, 2)[0]]
    sets = [good, dep3, two, four]; order = list(range(4)); rng.shuffle(order)
    options = [{"objects": {"S": obj_vectors(sets[i])}, "verifier": {"op": "is_basis", "args": {"vectors": {"ref": "S"}, "ambient_dim": 3}}} for i in order]
    ans = order.index(0)
    c = _base("basis", role, difficulty, "definition", "basis_selection")
    c.update(objects={}, stem_template="下列哪一組向量是 $\\mathbb{R}^3$ 的基底?(基底必須線性獨立且張成整個空間)", verify_mode="predicate", options=options, answer_index=ans,
             explanation_template="$\\mathbb{R}^3$ 的基底恰好含 3 個線性獨立向量。向量太少無法張成空間,向量太多或線性相依則不是基底。", explanation_answer_index=ans)
    return _fill_section(c)


def inverse_2x2(rng, difficulty, role):
    for _ in range(200):
        A = rand_matrix(rng, 2, 2, -3, 3); d = A[0][0] * A[1][1] - A[0][1] * A[1][0]
        if d != 0 and abs(d) != 1: break
    inv = fracla.inverse(fracla.to_mat(A))
    adj = [[A[1][1], -A[0][1]], [-A[1][0], A[0][0]]]
    inv_t = [list(r) for r in zip(*inv)]
    c = _base("inverse", role, difficulty, "computation", "inverse_2x2")
    c.update(objects={"A": obj_matrix(A)}, stem_template="求 {{A}} 的反矩陣 $A^{-1}$。", verify_mode="value", verifier={"op": "inverse", "args": {"matrix": {"ref": "A"}}},
             explanation_template=f"$A^{{-1}}=\\dfrac{{1}}{{\\det A}}\\operatorname{{adj}}(A)$,其中 $\\det A={d}$。", explanation_claim=c_mat(inv))
    c["options"], c["answer_index"] = _options(rng, c_mat(inv), [c_mat(adj), c_mat(inv_t), c_mat([[-x for x in r] for r in inv]), c_mat([[Fraction(A[1][1], d), Fraction(A[0][1], d)], [Fraction(A[1][0], d), Fraction(A[0][0], d)]])])
    return _fill_section(c)


def eigenvalues_2x2(rng, difficulty, role):
    for _ in range(200):
        d1, d2 = rng.randint(-3, 4), rng.randint(-3, 4)
        a = rng.choice([-2, -1, 1, 2])
        if d1 != d2: break
    P, Pinv, D = [[1, a], [0, 1]], [[1, -a], [0, 1]], [[d1, 0], [0, d2]]
    A = matmul(matmul(P, D), Pinv)
    tr = d1 + d2
    c = _base("eigenvalues", role, difficulty, "computation", "eigenvalues_2x2")
    c.update(objects={"A": obj_matrix(A)}, stem_template="求 {{A}} 的所有特徵值。", verify_mode="value", verifier={"op": "eigenvalues", "args": {"matrix": {"ref": "A"}}},
             explanation_template="特徵值是特徵多項式 $\\det(A-\\lambda I)=0$ 的根;可用 $\\lambda_1+\\lambda_2=\\operatorname{tr}(A)$ 與 $\\lambda_1\\lambda_2=\\det(A)$ 檢查。", explanation_claim=c_set([d1, d2]))
    c["options"], c["answer_index"] = _options(rng, c_set([d1, d2]), [c_set([-d1, -d2]), c_set([d1, -d2]), c_set([-d1, d2]), c_set([d1 + 1, d2]), c_set([d1, d2 + 1]), c_set([tr, d1 * d2])])
    return _fill_section(c)


def projection_vec(rng, difficulty, role):
    while True:
        a, b = [rng.randint(-3, 3) for _ in range(3)], [rng.randint(-3, 3) for _ in range(3)]
        dot, aa = sum(x * y for x, y in zip(a, b)), sum(x * x for x in a)
        if aa and dot: break
    proj = [Fraction(dot, aa) * x for x in a]
    c = _base("projection", role, difficulty, "computation", "projection_vec")
    c.update(objects={"a": {"kind": "vector", "data": a}, "b": {"kind": "vector", "data": b}}, stem_template="求向量 {{b}} 在向量 {{a}} 方向上的正交投影。", verify_mode="value",
             verifier={"op": "projection", "args": {"a": {"ref": "a"}, "b": {"ref": "b"}}},
             explanation_template="$\\operatorname{proj}_{a}b=\\dfrac{a\\cdot b}{a\\cdot a}\\,a$。", explanation_claim=c_vec(proj))
    bb = sum(x * x for x in b)
    c["options"], c["answer_index"] = _options(rng, c_vec(proj), [c_vec([dot * x for x in a]), c_vec([Fraction(dot, bb) * x for x in b] if bb else [0, 0, 0]), c_vec([-x for x in proj]), c_vec([Fraction(dot, aa) * x for x in b])], [c_vec([2 * x for x in proj]), c_vec([x / 2 for x in proj]), c_vec([x + 1 for x in proj]), c_vec([x - 1 for x in proj])])
    return _fill_section(c)


TEMPLATES: Dict[str, Any] = {
    "rank_computation": rank_computation, "nullity_computation": nullity_computation, "det3": det3,
    "independence_definition": independence_definition, "independence_rref": independence_rref, "independence_param": independence_param,
    "counterexample_product_zero": counterexample_product_zero, "basis_selection": basis_selection, "inverse_2x2": inverse_2x2,
    "eigenvalues_2x2": eigenvalues_2x2, "projection_vec": projection_vec,
}


def make(template_id: str, seed: int, difficulty: int, role: str) -> Dict[str, Any]:
    return TEMPLATES[template_id](random.Random(f"{template_id}:{seed}:{difficulty}:{role}"), difficulty, role)


def make_valid(template_id: str, seed: int, difficulty: int, role: str, ctx, tries: int = 6):
    """模板偶爾會因為隨機結果湊不出足夠的干擾選項(RuntimeError)或驗證不通過:換一個種子重試,有次數上限。
    回傳 (通過驗證的題目 或 None, 嘗試次數, 失敗紀錄)"""
    from . import validate
    fails = []
    for i in range(tries):
        try:
            c = make(template_id, seed * 100 + i, difficulty, role)
        except RuntimeError as e:
            fails.append({"stage": "TEMPLATE_BUILD", "code": "BUILD_FAILED", "detail": str(e)}); continue
        r = validate.validate_candidate(c, ctx)
        if r.ok: return c, i + 1, fails
        fails += r.failures
    return None, tries, fails
