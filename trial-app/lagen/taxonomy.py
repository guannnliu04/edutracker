"""細緻的基礎觀念分類(草案)。
**小節編號是占位**:真正的對應必須等到取得教材目錄後才能確認(見規格 §8)。這裡只示範資料結構。"""
TAXONOMY = {
    "linear-system": "1.2", "rref": "1.3",
    "matrix-ops": "2.1", "matrix-properties": "2.2", "inverse": "2.3",
    "determinant": "3.1",
    "subspace": "4.1", "span": "4.2", "linear-independence": "4.3", "basis": "4.4", "dimension": "4.5",
    "rank": "5.1", "nullity": "5.2", "rank-nullity": "5.3",
    "linear-transformation": "6.1",
    "eigenvalues": "7.1",
    "projection": "8.1",
}
# 「基礎」角色可以使用的觀念(題目角色 ≠ 難度 ≠ 來源;這只限制哪些觀念能擔任基礎格)
BASIC_ELIGIBLE = {"matrix-properties", "matrix-ops", "linear-independence", "span", "basis", "dimension", "rank", "nullity", "rref", "inverse", "subspace"}
