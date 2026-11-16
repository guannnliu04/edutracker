import { describe, expect, it } from "vitest";
import { conceptStats, weekSummary } from "./weakness";
import type { Attempt } from "../types";

const at = (date: string, conceptId: string, correct: boolean, unsure = false): Attempt => ({
  id: `${date}:${conceptId}:${correct}`,
  date,
  questionId: "q",
  conceptId,
  slot: "basic",
  selected: "o1",
  correct,
  unsure,
});

describe("觀念弱點", () => {
  it("只列出錯過或不確定的觀念,並依弱點分數排序", () => {
    const stats = conceptStats([
      at("2026-11-01", "A", true),
      at("2026-11-02", "B", false),
      at("2026-11-03", "B", true),
      at("2026-11-04", "C", true, true),
    ]);
    expect(stats.map((s) => s.conceptId)).toEqual(["B", "C"]);
    expect(stats[0].score).toBeCloseTo(0.5);
    expect(stats[1].score).toBeCloseTo(0.5);
  });

  it("先答對後答錯算一次遺忘", () => {
    const [s] = conceptStats([at("2026-11-01", "A", true), at("2026-11-08", "A", false)]);
    expect(s.forgot).toBe(1);
    expect(s.lastWrong).toBe("2026-11-08");
  });

  it("答錯在先、之後才答對不算遺忘", () => {
    const [s] = conceptStats([at("2026-11-01", "A", false), at("2026-11-02", "A", true)]);
    expect(s.forgot).toBe(0);
  });

  it("本週摘要統計正確率、不確定與錯誤類型", () => {
    const w = weekSummary(
      [
        at("2026-11-10", "A", false),
        { ...at("2026-11-11", "A", false), errorType: "careless" },
        at("2026-11-12", "A", true, true),
        at("2026-10-01", "A", false),
      ],
      "2026-11-10",
    );
    expect(w).toEqual({ attempts: 3, correct: 1, unsure: 1, byError: { careless: 1 } });
  });
});
