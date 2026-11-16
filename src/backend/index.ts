import type { Backend } from "./types";

// vite.config.ts 在正式建置時把它設為 false,讓本機示範模式(含題庫答案)被整段排除
declare const __LOCAL_BACKEND__: boolean;

export async function createBackend(): Promise<Backend> {
  const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
  if (url && key) {
    const { createSupabaseBackend } = await import("./supabase");
    return createSupabaseBackend(url, key);
  }
  if (__LOCAL_BACKEND__) {
    const { createLocalBackend } = await import("./local");
    return createLocalBackend();
  }
  throw new Error("缺少 VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY,請依 docs/SETUP.md 設定。");
}
