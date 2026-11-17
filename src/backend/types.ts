import type {
  AppState,
  DailySession,
  DraftAnswer,
  ErrorType,
  PracticeInput,
  QuestionMeta,
  ResultItem,
  StudyTask,
} from "../types";

export interface QuestionKey {
  correctOptionId: string;
  explanation: string;
}

/** 前端只透過這個介面存取資料,不知道底層是 Supabase 還是本機示範模式 */
export interface Backend {
  mode: "supabase" | "local";
  /** 目前登入者的 email;未登入回傳 null */
  getUser(): Promise<string | null>;
  signIn(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
  loadQuestions(): Promise<QuestionMeta[]>;
  loadState(today: string): Promise<AppState>;
  /** 已存在同日測驗時不覆蓋(多裝置同時開啟) */
  createSession(session: DailySession): Promise<void>;
  saveDraft(date: string, draft: Record<string, DraftAnswer>): Promise<void>;
  /** 伺服器評分;回傳逐題結果(含正解與解析) */
  submit(date: string): Promise<ResultItem[]>;
  getResults(date: string): Promise<ResultItem[]>;
  getKey(questionId: string): Promise<QuestionKey>;
  setErrorType(attemptId: string, type: ErrorType): Promise<void>;
  setChapter(chapter: number): Promise<void>;
  addTask(task: Pick<StudyTask, "date" | "title" | "subject" | "minutes">): Promise<void>;
  toggleTask(id: string, done: boolean): Promise<void>;
  deleteTask(id: string): Promise<void>;
  /** 匯入 GPT 練習紀錄;回傳實際新增的筆數(重複的會略過) */
  importPractice(logs: PracticeInput[]): Promise<number>;
  /** 僅本機示範模式支援 */
  reset?(): Promise<void>;
}
