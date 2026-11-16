import type { Concept } from "../types";

export const CHAPTERS: Record<number, string> = {
  1: "線性方程組與高斯消去",
  2: "矩陣運算與反矩陣",
  3: "向量空間與子空間",
  4: "線性獨立、基底與維度",
  5: "線性轉換與秩—零度定理",
  6: "行列式",
  7: "特徵值與對角化",
  8: "內積與正交",
};

export const CONCEPTS: Concept[] = [
  { id: "linear-system", name: "線性方程組解的結構" },
  { id: "inverse", name: "反矩陣與可逆等價條件" },
  { id: "subspace", name: "子空間判定" },
  { id: "span-dim", name: "生成空間與維度" },
  { id: "rank-nullity", name: "秩—零度定理" },
  { id: "dim-formula", name: "子空間維度公式" },
  { id: "rank-ineq", name: "秩的不等式" },
  { id: "det-properties", name: "行列式性質" },
  { id: "eigen-basic", name: "特徵值計算" },
  { id: "diagonalizable", name: "可對角化判定" },
  { id: "eigen-functions", name: "特徵值與矩陣函數" },
  { id: "symmetric-spectral", name: "實對稱矩陣" },
  { id: "projection", name: "正交投影" },
  { id: "orthogonal-matrix", name: "正交矩陣" },
  { id: "idempotent", name: "冪等矩陣" },
  { id: "skew-symmetric", name: "斜對稱矩陣" },
  { id: "gram-matrix", name: "AᵀA 與秩" },
];

export const conceptName = (id: string): string =>
  CONCEPTS.find((c) => c.id === id)?.name ?? id;
