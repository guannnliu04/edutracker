import type { Attempt, ReviewItem } from "../types";
import { addDays } from "./date";

export const REVIEW_STAGES = [1, 3, 7] as const;

/** 答錯後排定隔日、3 日、7 日複習;同一觀念尚未完成的舊排程會被取代 */
export function scheduleReviews(
  existing: ReviewItem[],
  wrong: Attempt,
): ReviewItem[] {
  const kept = existing.filter(
    (r) => r.done || r.conceptId !== wrong.conceptId,
  );
  const created: ReviewItem[] = REVIEW_STAGES.map((stage) => ({
    id: `${wrong.questionId}:${wrong.date}:${stage}`,
    originQuestionId: wrong.questionId,
    conceptId: wrong.conceptId,
    dueDate: addDays(wrong.date, stage),
    stage,
    done: false,
  }));
  return [...kept, ...created];
}

export const dueReviews = (reviews: ReviewItem[], date: string): ReviewItem[] =>
  reviews
    .filter((r) => !r.done && r.dueDate <= date)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate) || a.stage - b.stage);
