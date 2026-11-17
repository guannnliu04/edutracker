import type { AppState } from "../types";

/**
 * 第一階段:資料存在這台裝置的 localStorage。
 * 第二階段改接 Supabase 時,只需要換掉這個介面的實作。
 */
export interface Storage {
  load(): AppState;
  save(state: AppState): void;
}

const KEY = "la-daily-quiz:v1";

export const emptyState = (): AppState => ({
  version: 1,
  settings: { currentChapter: 7 },
  sessions: [],
  attempts: [],
  reviews: [],
  tasks: [],
  practice: [],
});

export const localStorageAdapter: Storage = {
  load() {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (!raw) return emptyState();
      const parsed = JSON.parse(raw) as AppState;
      if (parsed.version !== 1) return emptyState();
      return { ...emptyState(), ...parsed };
    } catch {
      return emptyState();
    }
  },
  save(state) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      // 私密瀏覽或容量不足時,至少讓 App 繼續運作
    }
  },
};
