// 本機示範模式(只用於開發與測試;正式建置會被排除,題庫答案不會進入正式版 bundle)
import type { AppState, DailySession, QuestionMeta, ResultItem } from "../types";
import { QUESTIONS } from "../data/questions";
import { emptyState, localStorageAdapter } from "../lib/storage";
import { getQuestion, setErrorType, submitSession, updateSession } from "../lib/session";
import type { Backend } from "./types";

const metas: QuestionMeta[] = QUESTIONS.map((q) => ({
  id: q.id,
  kind: q.kind,
  chapter: q.chapter,
  conceptId: q.conceptId,
  prompt: q.prompt,
  options: q.options.map(({ id, text }) => ({ id, text })),
  origin: q.origin,
}));

export function createLocalBackend(): Backend {
  let state: AppState = localStorageAdapter.load();
  const commit = (next: AppState) => {
    state = next;
    localStorageAdapter.save(state);
  };

  const results = (date: string): ResultItem[] => {
    const session = state.sessions.find((s) => s.date === date);
    if (!session?.submittedAt) throw new Error("尚未提交");
    return session.slots.flatMap((sl): ResultItem[] => {
      const a = state.attempts.find((x) => x.date === date && x.questionId === sl.questionId);
      if (!a) return [];
      const q = getQuestion(sl.questionId);
      return [{
        attemptId: a.id,
        questionId: q.id,
        selected: a.selected,
        correct: a.correct,
        unsure: a.unsure,
        errorType: a.errorType,
        correctOptionId: q.options.find((o) => o.isCorrect)!.id,
        explanation: q.explanation,
      }];
    });
  };

  return {
    mode: "local",
    getUser: async () => "本機示範",
    signIn: async () => {},
    signOut: async () => {},
    loadQuestions: async () => metas,
    loadState: async () => state,
    createSession: async (session: DailySession) => {
      if (state.sessions.some((s) => s.date === session.date)) return;
      commit({ ...state, sessions: [...state.sessions, session] });
    },
    saveDraft: async (date, draft) => {
      commit(updateSession(state, date, (s) => ({ ...s, draft })));
    },
    submit: async (date) => {
      commit(submitSession(state, date, new Date().toISOString()));
      return results(date);
    },
    getResults: async (date) => results(date),
    getKey: async (questionId) => {
      const q = getQuestion(questionId);
      return { correctOptionId: q.options.find((o) => o.isCorrect)!.id, explanation: q.explanation };
    },
    setErrorType: async (attemptId, type) => commit(setErrorType(state, attemptId, type)),
    setChapter: async (chapter) => commit({ ...state, settings: { ...state.settings, currentChapter: chapter } }),
    addTask: async (t) =>
      commit({ ...state, tasks: [...state.tasks, { ...t, id: crypto.randomUUID(), done: false }] }),
    toggleTask: async (id, done) =>
      commit({ ...state, tasks: state.tasks.map((t) => (t.id === id ? { ...t, done } : t)) }),
    deleteTask: async (id) => commit({ ...state, tasks: state.tasks.filter((t) => t.id !== id) }),
    reset: async () => commit(emptyState()),
  };
}
