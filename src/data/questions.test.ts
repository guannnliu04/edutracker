import { describe, expect, it } from "vitest";
import { QUESTIONS } from "./questions";
import { CONCEPTS } from "./concepts";

describe("題庫驗證", () => {
  it("題目 id 不重複", () => {
    expect(new Set(QUESTIONS.map((q) => q.id)).size).toBe(QUESTIONS.length);
  });

  for (const q of QUESTIONS) {
    describe(q.id, () => {
      it("恰有 4 個選項且只有 1 個正確答案", () => {
        expect(q.options).toHaveLength(4);
        expect(q.options.filter((o) => o.isCorrect)).toHaveLength(1);
      });
      it("選項文字不重複", () => {
        expect(new Set(q.options.map((o) => o.text)).size).toBe(4);
      });
      it("觀念 id 存在,且有解析", () => {
        expect(CONCEPTS.some((c) => c.id === q.conceptId)).toBe(true);
        expect(q.explanation.length).toBeGreaterThan(10);
      });
      it("解析不使用會因打亂而失效的位置用語", () => {
        expect(q.explanation).not.toMatch(/選項\s*[A-D]/);
      });
      it("非原題不可冒稱歷屆作業;歷屆作業必須附出處", () => {
        if (q.origin === "past-homework") expect(q.sourceRef).toBeTruthy();
        else expect(q.sourceRef).toBeUndefined();
      });
    });
  }

  it("每種題型都足夠支撐每日配置", () => {
    expect(QUESTIONS.filter((q) => q.kind === "basic").length).toBeGreaterThanOrEqual(3);
    expect(QUESTIONS.filter((q) => q.kind === "chapter").length).toBeGreaterThanOrEqual(1);
    expect(QUESTIONS.filter((q) => q.kind === "homework").length).toBeGreaterThanOrEqual(1);
  });
});
