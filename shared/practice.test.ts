import { describe, expect, it } from "vitest";
import { PRACTICE_EXAMPLE, parsePracticeRecord } from "./practice";

const TODAY = "2026-11-18";
const item = (over: Record<string, unknown> = {}) => ({
  concept: "eigen-basic",
  prompt: "矩陣的特徵值為何?",
  myAnswer: "C",
  correctAnswer: "B",
  correct: false,
  ...over,
});
const ok = (raw: unknown) => {
  const r = parsePracticeRecord(raw, TODAY);
  if (!r.ok) throw new Error(r.error);
  return r.logs;
};
const err = (raw: unknown) => {
  const r = parsePracticeRecord(raw, TODAY);
  if (r.ok) throw new Error("應該失敗");
  return r.error;
};

describe("GPT 練習紀錄驗證", () => {
  it("官方範例本身必須通過", () => {
    expect(ok(PRACTICE_EXAMPLE)).toHaveLength(1);
  });

  it("可以是物件或直接是陣列;沒給 date 就用今天", () => {
    expect(ok({ items: [item()] })[0].date).toBe(TODAY);
    expect(ok([item()])[0].date).toBe(TODAY);
  });

  it("unsure 預設 false;答對的題目不記錯誤類型", () => {
    const [a] = ok([item({ correct: true, myAnswer: "B", errorType: "careless" })]);
    expect(a.unsure).toBe(false);
    expect(a.errorType).toBeUndefined();
  });

  it("整批退回,並指出第幾題哪個欄位", () => {
    expect(err([item(), item({ prompt: "" })])).toMatch(/第 2 題:prompt/);
    expect(err([item({ correct: "yes" })])).toMatch(/第 1 題:correct/);
  });

  it("字母答案與 correct 矛盾要擋下(GPT 記錄錯誤)", () => {
    expect(err([item({ myAnswer: "B", correctAnswer: "B", correct: false })])).toMatch(/矛盾/);
    expect(err([item({ myAnswer: "A", correctAnswer: "B", correct: true })])).toMatch(/矛盾/);
  });

  it("非字母答案(例如數值)不做一致性檢查", () => {
    expect(ok([item({ myAnswer: "(2,2,2)", correctAnswer: "(2, 2, 2)", correct: true })])).toHaveLength(1);
  });

  it("日期必須存在且不能在未來", () => {
    expect(err({ date: "2026-02-30", items: [item()] })).toMatch(/有效日期/);
    expect(err({ date: "2027-01-01", items: [item()] })).toMatch(/未來/);
    expect(err({ date: "11/18", items: [item()] })).toMatch(/長度|格式/);
  });

  it("數量與長度限制", () => {
    expect(err({ items: [] })).toMatch(/1~20/);
    expect(err({ items: Array(21).fill(item()) })).toMatch(/1~20/);
    expect(err([item({ prompt: "x".repeat(2001) })])).toMatch(/長度/);
    expect(err([item({ errorType: "lazy" })])).toMatch(/errorType/);
    expect(err([item({ options: ["only one"] })])).toMatch(/options/);
  });

  it("不是物件或陣列", () => {
    expect(err("hello")).toMatch(/JSON/);
    expect(err(null)).toMatch(/JSON/);
  });
});
