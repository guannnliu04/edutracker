"""第二套獨立實作:純 Python Fraction 的精確線性代數(不使用 SymPy)。
用途:和 SymPy 結果做差異比對(differential testing)。兩套實作任何不一致都視為驗證失敗。"""
from fractions import Fraction
from typing import List, Optional, Sequence

Mat = List[List[Fraction]]


def to_mat(rows: Sequence[Sequence]) -> Mat:
    return [[Fraction(x) for x in r] for r in rows]


def rref(m: Mat) -> tuple:
    a = [r[:] for r in m]
    rows, cols = len(a), len(a[0]) if a else 0
    pivots, r = [], 0
    for c in range(cols):
        p = next((i for i in range(r, rows) if a[i][c] != 0), None)
        if p is None:
            continue
        a[r], a[p] = a[p], a[r]
        pv = a[r][c]
        a[r] = [x / pv for x in a[r]]
        for i in range(rows):
            if i != r and a[i][c] != 0:
                f = a[i][c]
                a[i] = [x - f * y for x, y in zip(a[i], a[r])]
        pivots.append(c)
        r += 1
        if r == rows:
            break
    return a, pivots


def rank(m: Mat) -> int:
    return len(rref(m)[1])


def det(m: Mat) -> Fraction:
    n = len(m)
    assert all(len(r) == n for r in m)
    a = [r[:] for r in m]
    d = Fraction(1)
    for c in range(n):
        p = next((i for i in range(c, n) if a[i][c] != 0), None)
        if p is None:
            return Fraction(0)
        if p != c:
            a[c], a[p] = a[p], a[c]
            d = -d
        d *= a[c][c]
        for i in range(c + 1, n):
            f = a[i][c] / a[c][c]
            a[i] = [x - f * y for x, y in zip(a[i], a[c])]
    return d


def inverse(m: Mat) -> Optional[Mat]:
    n = len(m)
    aug = [m[i][:] + [Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    red, piv = rref(aug)
    if piv[:n] != list(range(n)):
        return None
    return [r[n:] for r in red]


def transpose(m: Mat) -> Mat:
    return [list(c) for c in zip(*m)]


def matmul(a: Mat, b: Mat) -> Mat:
    bt = transpose(b)
    return [[sum(x * y for x, y in zip(r, c)) for c in bt] for r in a]
