// 給 GPT 的「今天該複習什麼、哪裡最弱」。純函式,方便測試。
// 只能匯入「葉節點」模組(沒有其他執行期匯入),Vercel 在 Node ESM 下才跑得起來,所以匯入要寫 .js。
import type { Attempt } from "../src/types";
import { addDays } from "../src/lib/date.js";
import { conceptStats } from "../src/lib/weakness.js";
import { CONCEPTS, CHAPTERS } from "../src/data/concepts.js";

/** App 內作答與 GPT 練習統一成這個形狀 */
export interface LogRow {
  date: string;
  concept: string;
  correct: boolean;
  unsure: boolean;
  errorType?: string;
  prompt?: string;
  myAnswer?: string;
  correctAnswer?: string;
}

const STAGES = [1, 3, 7] as const;
const GRACE_DAYS = 14; // 答錯後 14 天內都還算待複習

export interface DueReview {
  concept: string;
  lastWrongDate: string;
  stage: 1 | 3 | 7;
  /** 當時答錯的那題,讓 GPT 出「變式」 */
  sourcePrompt?: string;
}

export function buildContext(rows: LogRow[], today: string) {
  const asAttempts = rows.map(
    (r, i): Attempt => ({
      id: String(i),
      date: r.date,
      questionId: String(i),
      conceptId: r.concept,
      slot: "basic",
      selected: "",
      correct: r.correct,
      unsure: r.unsure,
      errorType: r.errorType as Attempt["errorType"],
    }),
  );

  const weakConcepts = conceptStats(asAttempts)
    .slice(0, 10)
    .map((s) => ({
      concept: s.conceptId,
      attempts: s.attempts,
      wrong: s.wrong,
      unsureButCorrect: s.unsureRight,
      forgot: s.forgot,
      weakness: Math.round(s.score * 100) / 100,
      lastWrong: s.lastWrong,
    }));

  // 每個觀念取「最近一次答錯」,算隔日/3 日/7 日複習有沒有到、有沒有做過
  const byConcept = new Map<string, LogRow[]>();
  for (const r of rows) byConcept.set(r.concept, [...(byConcept.get(r.concept) ?? []), r]);

  const dueReviews: DueReview[] = [];
  for (const [concept, list] of byConcept) {
    const wrongs = list.filter((r) => !r.correct).sort((a, b) => b.date.localeCompare(a.date));
    const last = wrongs[0];
    if (!last || today > addDays(last.date, GRACE_DAYS)) continue;
    let stage: DueReview["stage"] | undefined;
    for (const s of STAGES) {
      const due = addDays(last.date, s);
      if (due > today) break;
      const practicedSince = list.some((r) => r.date >= due);
      if (!practicedSince) stage = s;
    }
    if (stage) dueReviews.push({ concept, lastWrongDate: last.date, stage, sourcePrompt: last.prompt });
  }
  dueReviews.sort((a, b) => a.lastWrongDate.localeCompare(b.lastWrongDate));

  const recentWrong = rows
    .filter((r) => !r.correct && r.prompt)
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 10)
    .map((r) => ({
      date: r.date,
      concept: r.concept,
      prompt: r.prompt,
      myAnswer: r.myAnswer,
      correctAnswer: r.correctAnswer,
      errorType: r.errorType,
    }));

  const total = rows.length;
  return {
    today,
    summary: {
      totalAnswered: total,
      correctRate: total ? Math.round((rows.filter((r) => r.correct).length / total) * 100) / 100 : null,
    },
    dueReviews,
    weakConcepts,
    recentWrong,
    preferredConceptIds: CONCEPTS.map((c) => ({ id: c.id, name: c.name })),
    chapters: CHAPTERS,
  };
}
