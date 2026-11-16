import type { AppState, Question, SessionSlot } from "../types";
import { addDays } from "./date";
import { dueReviews } from "./review";
import { seededRng, shuffle } from "./rng";

/**
 * 每日五題:3 題基礎觀念與舊錯題、1 題最新章節、1 題作業風格。
 * 到期的舊錯題優先(同觀念的「變式」優先於原題),其餘空位由基礎題補滿。
 */
export function selectDaily(
  date: string,
  bank: readonly Question[],
  state: AppState,
): SessionSlot[] {
  const rng = seededRng(`slots:${date}`);
  const byId = new Map(bank.map((q) => [q.id, q]));
  const picked = new Set<string>();
  const slots: SessionSlot[] = [];

  const recentCutoff = addDays(date, -7);
  const recentlyAsked = new Set(
    state.attempts.filter((a) => a.date >= recentCutoff && a.date < date).map((a) => a.questionId),
  );
  const everAsked = new Set(state.attempts.map((a) => a.questionId));
  const wrongCountByConcept = new Map<string, number>();
  for (const a of state.attempts) {
    if (!a.correct) wrongCountByConcept.set(a.conceptId, (wrongCountByConcept.get(a.conceptId) ?? 0) + 1);
  }

  const take = (q: Question | undefined, slot: SessionSlot["slot"], reviewId?: string): boolean => {
    if (!q || picked.has(q.id)) return false;
    picked.add(q.id);
    slots.push({ questionId: q.id, slot, reviewId });
    return true;
  };

  // 1) 到期的舊錯題複習(最多 3 題)
  for (const r of dueReviews(state.reviews, date)) {
    if (slots.length >= 3) break;
    const sameConcept = bank.filter((q) => q.conceptId === r.conceptId && !picked.has(q.id));
    const variants = shuffle(sameConcept.filter((q) => q.id !== r.originQuestionId), rng);
    const origin = byId.get(r.originQuestionId);
    take(variants[0] ?? (origin && !picked.has(origin.id) ? origin : undefined), "review", r.id);
  }

  // 2) 基礎題補滿 3 題:弱點觀念優先,近 7 天出過的延後
  const basics = shuffle(
    bank.filter((q) => q.kind === "basic" && !picked.has(q.id)),
    rng,
  ).sort((a, b) => {
    const recent = Number(recentlyAsked.has(a.id)) - Number(recentlyAsked.has(b.id));
    if (recent) return recent;
    return (wrongCountByConcept.get(b.conceptId) ?? 0) - (wrongCountByConcept.get(a.conceptId) ?? 0);
  });
  for (const q of basics) {
    if (slots.length >= 3) break;
    take(q, "basic");
  }

  // 3) 最新章節 1 題:沒做過的優先;章節不夠時退到較早章節
  const current = state.settings.currentChapter;
  const chapterPool = shuffle(
    bank.filter((q) => q.kind === "chapter" && q.chapter <= current && !picked.has(q.id)),
    rng,
  ).sort(
    (a, b) =>
      Number(everAsked.has(a.id)) - Number(everAsked.has(b.id)) ||
      Number(b.chapter === current) - Number(a.chapter === current),
  );
  take(chapterPool[0], "chapter");

  // 4) 作業風格 1 題
  const hwPool = shuffle(
    bank.filter((q) => q.kind === "homework" && !picked.has(q.id)),
    rng,
  ).sort((a, b) => Number(everAsked.has(a.id)) - Number(everAsked.has(b.id)));
  take(hwPool[0], "homework");

  // 5) 題庫不足時,用任何沒選過的題補到五題
  for (const q of shuffle(bank.filter((q) => !picked.has(q.id)), rng)) {
    if (slots.length >= 5) break;
    take(q, "basic");
  }

  return slots;
}
