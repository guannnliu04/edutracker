import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type {
  AppState,
  Attempt,
  DailySession,
  DraftAnswer,
  ErrorType,
  PracticeInput,
  PracticeLog,
  QuestionMeta,
  ResultItem,
  ReviewItem,
  SessionSlot,
  StudyTask,
} from "../types";
import { addDays } from "../lib/date";
import { emptyState } from "../lib/storage";
import type { Backend, QuestionKey } from "./types";

function fail(error: { message: string } | null): asserts error is null {
  if (error) throw new Error(error.message);
}

export function createSupabaseBackend(url: string, anonKey: string): Backend {
  // anon key 設計上可公開;資料安全靠資料庫的 RLS 與欄位權限(見 supabase/migrations)
  const sb: SupabaseClient = createClient(url, anonKey, {
    auth: { persistSession: true, autoRefreshToken: true },
  });

  const userId = async (): Promise<string> => {
    const { data } = await sb.auth.getSession();
    if (!data.session) throw new Error("尚未登入");
    return data.session.user.id;
  };

  return {
    mode: "supabase",

    async getUser() {
      const { data } = await sb.auth.getSession();
      return data.session?.user.email ?? null;
    },

    async signIn(email, password) {
      const { error } = await sb.auth.signInWithPassword({ email, password });
      fail(error);
    },

    async signOut() {
      await sb.auth.signOut();
    },

    async loadQuestions() {
      const { data, error } = await sb
        .from("questions")
        .select("id, kind, chapter, concept_id, prompt, options, origin");
      fail(error);
      return (data ?? []).map(
        (r): QuestionMeta => ({
          id: r.id,
          kind: r.kind,
          chapter: r.chapter,
          conceptId: r.concept_id,
          prompt: r.prompt,
          options: r.options,
          origin: r.origin,
        }),
      );
    },

    async loadState(today) {
      const since = addDays(today, -14);
      const [settings, sessions, attempts, reviews, tasks, practice] = await Promise.all([
        sb.from("settings").select("current_chapter").maybeSingle(),
        sb.from("sessions").select("date, slots, draft, submitted_at").gte("date", since),
        sb.from("attempts").select("*").order("date"),
        sb.from("reviews").select("*").eq("done", false),
        sb.from("study_tasks").select("*").eq("date", today).order("created_at"),
        sb.from("practice_logs").select("*").order("date"),
      ]);
      for (const r of [settings, sessions, attempts, reviews, tasks, practice]) fail(r.error);

      const state: AppState = {
        ...emptyState(),
        settings: { currentChapter: settings.data?.current_chapter ?? 7 },
        sessions: (sessions.data ?? []).map(
          (s): DailySession => ({
            date: s.date,
            slots: s.slots as SessionSlot[],
            draft: (s.draft ?? {}) as Record<string, DraftAnswer>,
            submittedAt: s.submitted_at ?? undefined,
          }),
        ),
        attempts: (attempts.data ?? []).map(
          (a): Attempt => ({
            id: a.id,
            date: a.date,
            questionId: a.question_id,
            conceptId: a.concept_id,
            slot: a.slot,
            selected: a.selected,
            correct: a.correct,
            unsure: a.unsure,
            errorType: a.error_type ?? undefined,
          }),
        ),
        reviews: (reviews.data ?? []).map(
          (r): ReviewItem => ({
            id: r.id,
            originQuestionId: r.origin_question_id,
            conceptId: r.concept_id,
            dueDate: r.due_date,
            stage: r.stage,
            done: r.done,
          }),
        ),
        tasks: (tasks.data ?? []) as StudyTask[],
        practice: (practice.data ?? []).map(
          (p): PracticeLog => ({
            id: p.id,
            date: p.date,
            concept: p.concept,
            prompt: p.prompt,
            options: p.options ?? undefined,
            myAnswer: p.my_answer,
            correctAnswer: p.correct_answer,
            correct: p.correct,
            unsure: p.unsure,
            errorType: p.error_type ?? undefined,
            explanation: p.explanation ?? undefined,
          }),
        ),
      };
      return state;
    },

    async createSession(session) {
      const { error } = await sb
        .from("sessions")
        .upsert(
          { date: session.date, slots: session.slots, draft: session.draft },
          { onConflict: "user_id,date", ignoreDuplicates: true },
        );
      fail(error);
    },

    async saveDraft(date, draft) {
      const { error } = await sb.from("sessions").update({ draft }).eq("date", date);
      fail(error);
    },

    async submit(date) {
      const { data, error } = await sb.rpc("submit_session", { p_date: date });
      fail(error);
      return data as ResultItem[];
    },

    async getResults(date) {
      const { data, error } = await sb.rpc("get_results", { p_date: date });
      fail(error);
      return data as ResultItem[];
    },

    async getKey(questionId) {
      const { data, error } = await sb.rpc("get_key", { p_question_id: questionId });
      fail(error);
      return data as QuestionKey;
    },

    async setErrorType(attemptId, type: ErrorType) {
      const { error } = await sb.from("attempts").update({ error_type: type }).eq("id", attemptId);
      fail(error);
    },

    async setChapter(chapter) {
      const uid = await userId();
      const upd = await sb.from("settings").update({ current_chapter: chapter }).eq("user_id", uid).select();
      fail(upd.error);
      if (!upd.data?.length) {
        const { error } = await sb.from("settings").insert({ current_chapter: chapter });
        fail(error);
      }
    },

    async importPractice(logs: PracticeInput[]) {
      const rows = logs.map((l) => ({
        date: l.date,
        concept: l.concept,
        prompt: l.prompt,
        options: l.options ?? null,
        my_answer: l.myAnswer,
        correct_answer: l.correctAnswer,
        correct: l.correct,
        unsure: l.unsure,
        error_type: l.errorType ?? null,
        explanation: l.explanation ?? null,
      }));
      const { data, error } = await sb
        .from("practice_logs")
        .upsert(rows, { onConflict: "user_id,date,prompt_hash", ignoreDuplicates: true })
        .select("id");
      fail(error);
      return data?.length ?? 0;
    },

    async addTask(task) {
      const { error } = await sb.from("study_tasks").insert(task);
      fail(error);
    },

    async toggleTask(id, done) {
      const { error } = await sb.from("study_tasks").update({ done }).eq("id", id);
      fail(error);
    },

    async deleteTask(id) {
      const { error } = await sb.from("study_tasks").delete().eq("id", id);
      fail(error);
    },
  };
}
