import { describe, expect, it } from "vitest";
import { emptyState } from "./storage";
import { submitSession, updateSession, getQuestion } from "./session";
import { buildSession } from "./buildSession";
import { addDays } from "./date";
import { selectDaily } from "./selectDaily";
import { QUESTIONS } from "../data/questions";
import type { AppState } from "../types";

const ensureSession = (state: AppState, date: string): AppState => ({
  ...state,
  sessions: [...state.sessions, buildSession(date, QUESTIONS, state)],
});

const answerAll = (state: AppState, date: string, pickWrong: boolean): AppState =>
  updateSession(state, date, (s) => ({
    ...s,
    draft: Object.fromEntries(
      s.slots.map((sl) => {
        const q = getQuestion(sl.questionId);
        const opt = q.options.find((o) => o.isCorrect === !pickWrong)!;
        return [q.id, { selected: opt.id, unsure: false }];
      }),
    ),
  }));

describe("每日選題", () => {
  it("固定五題:3 基礎/複習、1 最新章節、1 作業風格,且不重複", () => {
    const slots = selectDaily("2026-11-16", QUESTIONS, emptyState());
    expect(slots).toHaveLength(5);
    expect(new Set(slots.map((s) => s.questionId)).size).toBe(5);
    const count = (k: string) => slots.filter((s) => s.slot === k).length;
    expect(count("basic") + count("review")).toBe(3);
    expect(count("chapter")).toBe(1);
    expect(count("homework")).toBe(1);
  });

  it("同一天重複產生結果相同", () => {
    const a = selectDaily("2026-11-16", QUESTIONS, emptyState());
    const b = selectDaily("2026-11-16", QUESTIONS, emptyState());
    expect(a).toEqual(b);
  });
});

describe("出題範圍(只出已讀到的章節)", () => {
  const stateAt = (currentChapter: number): AppState => ({ ...emptyState(), settings: { currentChapter } });
  const chapterOf = (id: string) => QUESTIONS.find((q) => q.id === id)!.chapter;

  it.each([3, 5, 7, 8])("讀到第 %i 章:五題都不超出範圍,且不重複", (ch) => {
    for (const d of ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]) {
      const slots = selectDaily(d, QUESTIONS, stateAt(ch));
      expect(slots.every((s) => chapterOf(s.questionId) <= ch)).toBe(true);
      expect(new Set(slots.map((s) => s.questionId)).size).toBe(slots.length);
    }
  });

  it("範圍內題目不夠時,寧可少出,也不出還沒讀的內容", () => {
    const slots = selectDaily("2026-11-16", QUESTIONS, stateAt(1));
    expect(slots.length).toBeGreaterThan(0);
    expect(slots.length).toBeLessThan(5);
    expect(slots.every((s) => chapterOf(s.questionId) <= 1)).toBe(true);
  });

  it("複習題的變式也只從範圍內挑", () => {
    // 先在第 8 章答錯 inverse 觀念的題,再把進度退到第 3 章:變式不可出第 8 章的題
    const st: AppState = {
      ...stateAt(3),
      reviews: [{ id: "r1", originQuestionId: "b09", conceptId: "symmetric-spectral", dueDate: "2026-11-16", stage: 1, done: false }],
    };
    const slots = selectDaily("2026-11-16", QUESTIONS, st);
    const review = slots.find((s) => s.slot === "review");
    expect(review === undefined || review.questionId === "b09" || chapterOf(review.questionId) <= 3).toBe(true);
  });
});

describe("作答與複習", () => {
  it("未全部作答不能提交", () => {
    const d = "2026-11-16";
    const s = ensureSession(emptyState(), d);
    expect(submitSession(s, d, "now").sessions[0].submittedAt).toBeUndefined();
  });

  it("答錯後排定 1/3/7 日複習,且隔日複習題優先出現", () => {
    const d = "2026-11-16";
    let s = answerAll(ensureSession(emptyState(), d), d, true);
    s = submitSession(s, d, "now");
    expect(s.attempts.every((a) => !a.correct)).toBe(true);
    // 同一觀念只保留最新一組排程,所以以「觀念」為單位檢查,每個答錯的觀念都有且只有 1/3/7 這一組
    for (const concept of new Set(s.attempts.map((a) => a.conceptId))) {
      const stages = s.reviews.filter((r) => r.conceptId === concept).map((r) => r.stage);
      expect(stages.sort()).toEqual([1, 3, 7]);
    }

    const next = addDays(d, 1);
    const slots = selectDaily(next, QUESTIONS, s);
    expect(slots.filter((x) => x.slot === "review").length).toBeGreaterThan(0);
    expect(slots).toHaveLength(5);
  });

  it("全部答對則沒有複習排程", () => {
    const d = "2026-11-16";
    let s = answerAll(ensureSession(emptyState(), d), d, false);
    s = submitSession(s, d, "now");
    expect(s.reviews).toHaveLength(0);
  });
});
