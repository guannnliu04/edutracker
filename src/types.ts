import type { PracticeInput } from "../shared/practice";
export type { PracticeInput };

export type QuestionKind = "basic" | "chapter" | "homework";
export type Slot = "review" | "basic" | "chapter" | "homework";
export type ErrorType = "concept" | "calculation" | "careless" | "guess";

export const ERROR_TYPE_LABEL: Record<ErrorType, string> = {
  concept: "觀念錯誤",
  calculation: "計算錯誤",
  careless: "粗心",
  guess: "猜的／不會",
};

export interface OptionMeta {
  id: string; // 穩定 id,不隨顯示順序改變
  text: string;
}

export interface Option extends OptionMeta {
  isCorrect: boolean;
}

/** 前端拿到的題目:不含正確答案與解析(那些只能在提交後由伺服器回傳) */
export interface QuestionMeta {
  id: string;
  kind: QuestionKind;
  chapter: number;
  conceptId: string;
  prompt: string;
  options: OptionMeta[];
  /** 'self-authored' = 自編題;只有取得原題並填入 sourceRef 才可標為 'past-homework' */
  origin: "self-authored" | "past-homework";
}

/** 完整題目(含答案),只存在於題庫檔、種子產生與本機示範模式 */
export interface Question extends Omit<QuestionMeta, "options"> {
  options: Option[];
  explanation: string; // 不可用「選項 A」這類位置用語,因為選項順序會被打亂
  sourceRef?: string;
}

/** 提交後由伺服器回傳的逐題結果 */
export interface ResultItem {
  attemptId: string;
  questionId: string;
  selected: string;
  correct: boolean;
  unsure: boolean;
  errorType?: ErrorType;
  correctOptionId: string;
  explanation: string;
}

/** ChatGPT 出題、你在 ChatGPT 作答後匯入的練習紀錄(對錯由 GPT 判定) */
export interface PracticeLog extends PracticeInput {
  id: string;
}

export interface StudyTask {
  id: string;
  date: string;
  title: string;
  subject: string;
  minutes: number;
  done: boolean;
}

export interface Concept {
  id: string;
  name: string;
}

export interface SessionSlot {
  questionId: string;
  slot: Slot;
  reviewId?: string;
}

export interface DraftAnswer {
  selected: string; // option id
  unsure: boolean;
}

export interface DailySession {
  date: string; // YYYY-MM-DD(裝置當地時間)
  slots: SessionSlot[];
  draft: Record<string, DraftAnswer>;
  submittedAt?: string;
}

export interface Attempt {
  id: string;
  date: string;
  questionId: string;
  conceptId: string;
  slot: Slot;
  selected: string;
  correct: boolean;
  unsure: boolean;
  errorType?: ErrorType;
}

export interface ReviewItem {
  id: string;
  originQuestionId: string;
  conceptId: string;
  dueDate: string;
  stage: 1 | 3 | 7;
  done: boolean;
}

export interface Settings {
  currentChapter: number;
}

export interface AppState {
  version: 1;
  settings: Settings;
  sessions: DailySession[];
  attempts: Attempt[];
  reviews: ReviewItem[];
  tasks: StudyTask[];
  practice: PracticeLog[];
}
