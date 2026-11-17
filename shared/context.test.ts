import { describe, expect, it } from "vitest";
import { buildContext, type LogRow } from "./context";

const row = (date: string, concept: string, correct: boolean, over: Partial<LogRow> = {}): LogRow => ({
  date,
  concept,
  correct,
  unsure: false,
  ...over,
});

describe("給 GPT 的複習脈絡", () => {
  it("答錯隔日到期,帶出當時那題讓 GPT 出變式", () => {
    const c = buildContext([row("2026-11-17", "eigen-basic", false, { prompt: "原題" })], "2026-11-18");
    expect(c.dueReviews).toEqual([
      { concept: "eigen-basic", lastWrongDate: "2026-11-17", stage: 1, sourcePrompt: "原題" },
    ]);
  });

  it("答錯當天還沒到期", () => {
    expect(buildContext([row("2026-11-18", "A", false)], "2026-11-18").dueReviews).toHaveLength(0);
  });

  it("到期日之後練習過該觀念就算複習完成", () => {
    const rows = [row("2026-11-10", "A", false), row("2026-11-11", "A", true)];
    expect(buildContext(rows, "2026-11-11").dueReviews).toHaveLength(0);
  });

  it("漏掉隔日複習,到第 3 天仍待複習並升到第 3 階段", () => {
    const c = buildContext([row("2026-11-10", "A", false)], "2026-11-13");
    expect(c.dueReviews[0].stage).toBe(3);
  });

  it("超過 14 天不再催", () => {
    expect(buildContext([row("2026-11-01", "A", false)], "2026-11-20").dueReviews).toHaveLength(0);
  });

  it("再次答錯會重新起算", () => {
    const rows = [row("2026-11-10", "A", false), row("2026-11-12", "A", false)];
    const c = buildContext(rows, "2026-11-13");
    expect(c.dueReviews[0]).toMatchObject({ lastWrongDate: "2026-11-12", stage: 1 });
  });

  it("弱點排行與最近錯題", () => {
    const c = buildContext(
      [row("2026-11-16", "A", true), row("2026-11-17", "A", false, { prompt: "p", myAnswer: "C", correctAnswer: "B" })],
      "2026-11-18",
    );
    expect(c.weakConcepts[0]).toMatchObject({ concept: "A", wrong: 1, forgot: 1 });
    expect(c.recentWrong[0]).toMatchObject({ prompt: "p", myAnswer: "C", correctAnswer: "B" });
    expect(c.summary).toEqual({ totalAnswered: 2, correctRate: 0.5 });
  });

  it("沒有資料時不爆", () => {
    const c = buildContext([], "2026-11-18");
    expect(c.summary.correctRate).toBeNull();
    expect(c.preferredConceptIds.length).toBeGreaterThan(5);
  });
});
