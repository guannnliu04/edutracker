import type { AppState, Attempt, DailySession, ErrorType, Question } from "../types";
import { scheduleReviews } from "./review";
import { QUESTIONS } from "../data/questions";

const bankById = new Map(QUESTIONS.map((q) => [q.id, q]));
export const getQuestion = (id: string): Question => {
  const q = bankById.get(id);
  if (!q) throw new Error(`Unknown question: ${id}`);
  return q;
};

export function updateSession(
  state: AppState,
  date: string,
  fn: (s: DailySession) => DailySession,
): AppState {
  return { ...state, sessions: state.sessions.map((s) => (s.date === date ? fn(s) : s)) };
}

/** 五題都有選擇後才能提交;提交後寫入作答紀錄並排定複習 */
export function submitSession(state: AppState, date: string, nowIso: string): AppState {
  const session = state.sessions.find((s) => s.date === date);
  if (!session || session.submittedAt) return state;
  if (!session.slots.every((sl) => session.draft[sl.questionId]?.selected)) return state;

  let reviews = state.reviews;
  const attempts: Attempt[] = [];
  for (const sl of session.slots) {
    const q = getQuestion(sl.questionId);
    const d = session.draft[sl.questionId];
    const correct = q.options.find((o) => o.id === d.selected)?.isCorrect ?? false;
    const attempt: Attempt = {
      id: `${date}:${q.id}`,
      date,
      questionId: q.id,
      conceptId: q.conceptId,
      slot: sl.slot,
      selected: d.selected,
      correct,
      unsure: d.unsure,
    };
    attempts.push(attempt);
    if (sl.reviewId) {
      reviews = reviews.map((r) => (r.id === sl.reviewId ? { ...r, done: true } : r));
    }
    if (!correct) reviews = scheduleReviews(reviews, attempt);
  }
  return {
    ...updateSession(state, date, (s) => ({ ...s, submittedAt: nowIso })),
    attempts: [...state.attempts.filter((a) => a.date !== date), ...attempts],
    reviews,
  };
}

export function setErrorType(
  state: AppState,
  attemptId: string,
  errorType: ErrorType,
): AppState {
  return {
    ...state,
    attempts: state.attempts.map((a) => (a.id === attemptId ? { ...a, errorType } : a)),
  };
}
