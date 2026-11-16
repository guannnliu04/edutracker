import type { Attempt, ErrorType } from "../types";

export interface ConceptStat {
  conceptId: string;
  attempts: number;
  wrong: number;
  /** 答對但勾了「不確定」 */
  unsureRight: number;
  /** 先前答對、之後又答錯的次數(遺忘) */
  forgot: number;
  /** (答錯 + 0.5×答對但不確定) ÷ 作答次數,0~1,越高越弱 */
  score: number;
  lastWrong?: string;
}

/** 觀念弱點排行:只列出至少錯過一次或答對但不確定的觀念 */
export function conceptStats(attempts: Attempt[]): ConceptStat[] {
  const byConcept = new Map<string, Attempt[]>();
  for (const a of attempts) byConcept.set(a.conceptId, [...(byConcept.get(a.conceptId) ?? []), a]);

  const stats: ConceptStat[] = [];
  for (const [conceptId, list] of byConcept) {
    const sorted = [...list].sort((a, b) => a.date.localeCompare(b.date));
    let seenCorrect = false;
    let forgot = 0;
    let wrong = 0;
    let unsureRight = 0;
    let lastWrong: string | undefined;
    for (const a of sorted) {
      if (a.correct) {
        seenCorrect = true;
        if (a.unsure) unsureRight++;
      } else {
        wrong++;
        lastWrong = a.date;
        if (seenCorrect) forgot++;
      }
    }
    if (wrong === 0 && unsureRight === 0) continue;
    stats.push({
      conceptId,
      attempts: sorted.length,
      wrong,
      unsureRight,
      forgot,
      score: (wrong + 0.5 * unsureRight) / sorted.length,
      lastWrong,
    });
  }
  return stats.sort(
    (a, b) => b.score - a.score || b.forgot - a.forgot || b.attempts - a.attempts,
  );
}

export interface WeekSummary {
  attempts: number;
  correct: number;
  unsure: number;
  byError: Partial<Record<ErrorType, number>>;
}

export function weekSummary(attempts: Attempt[], since: string): WeekSummary {
  const week = attempts.filter((a) => a.date >= since);
  const byError: WeekSummary["byError"] = {};
  for (const a of week) {
    if (!a.correct && a.errorType) byError[a.errorType] = (byError[a.errorType] ?? 0) + 1;
  }
  return {
    attempts: week.length,
    correct: week.filter((a) => a.correct).length,
    unsure: week.filter((a) => a.unsure).length,
    byError,
  };
}
