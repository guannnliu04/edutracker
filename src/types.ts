export type QuestionKind = "basic" | "chapter" | "homework";
export type Slot = "review" | "basic" | "chapter" | "homework";
export type ErrorType = "concept" | "calculation" | "careless" | "guess";

export const ERROR_TYPE_LABEL: Record<ErrorType, string> = {
  concept: "觀念錯誤",
  calculation: "計算錯誤",
  careless: "粗心",
  guess: "猜的／不會",
};

export interface Option {
  id: string; // 穩定 id,不隨顯示順序改變
  text: string;
  isCorrect: boolean;
}

export interface Question {
  id: string;
  kind: QuestionKind;
  chapter: number;
  conceptId: string;
  prompt: string;
  options: Option[];
  explanation: string; // 不可用「選項 A」這類位置用語,因為選項順序會被打亂
  /** 'self-authored' = 自編題;只有取得原題並填入 sourceRef 才可標為 'past-homework' */
  origin: "self-authored" | "past-homework";
  sourceRef?: string;
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
}
