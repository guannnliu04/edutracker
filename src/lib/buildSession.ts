import type { AppState, DailySession, QuestionMeta } from "../types";
import { selectDaily } from "./selectDaily";

export function buildSession(
  date: string,
  bank: readonly Pick<QuestionMeta, "id" | "kind" | "chapter" | "conceptId">[],
  state: AppState,
): DailySession {
  return { date, slots: selectDaily(date, bank, state), draft: {} };
}
