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
    const stages = s.reviews.filter((r) => r.originQuestionId === s.attempts[0].questionId).map((r) => r.stage);
    expect(stages.sort()).toEqual([1, 3, 7]);

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
