import type { Attempt, PracticeLog } from "../types";

/** 讓 GPT 練習紀錄能和 App 內作答一起進弱點統計 */
export const practiceAsAttempts = (logs: PracticeLog[]): Attempt[] =>
  logs.map((p) => ({
    id: p.id,
    date: p.date,
    questionId: p.id,
    conceptId: p.concept,
    slot: "basic",
    selected: p.myAnswer,
    correct: p.correct,
    unsure: p.unsure,
    errorType: p.errorType,
  }));
