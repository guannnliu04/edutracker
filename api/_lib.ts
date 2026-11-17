// 伺服器端共用:驗證 GPT 的金鑰、用「你自己的帳號」登入 Supabase 後以你的身分讀寫。
// 這樣不需要放高權限的 Supabase secret key:API 能做的事,不會超過你登入 App 能做的事(受 RLS 限制)。
import { createHash, timingSafeEqual } from "node:crypto";

export interface Req {
  method?: string;
  headers: Record<string, string | string[] | undefined>;
  body?: unknown;
}
export interface Res {
  status(code: number): Res;
  setHeader(name: string, value: string): Res;
  json(body: unknown): void;
}

export const env = (name: string, ...fallbacks: string[]): string | undefined =>
  [name, ...fallbacks].map((n) => process.env[n]).find((v) => v && v.length > 0);

/** 以固定長度雜湊後做常數時間比對,避免被量時間猜金鑰 */
export function checkBearer(req: Req, expected: string | undefined): boolean {
  if (!expected || expected.length < 20) return false; // 金鑰太短視為沒設定好,一律拒絕
  const h = req.headers["authorization"];
  const header = Array.isArray(h) ? h[0] : h;
  const given = header?.startsWith("Bearer ") ? header.slice(7).trim() : "";
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

export function todayInTz(tz = env("APP_TZ") ?? "Asia/Taipei", now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

interface Session {
  token: string;
  expiresAt: number;
}
let cached: Session | undefined;

async function ownerToken(url: string, anonKey: string): Promise<string> {
  if (cached && cached.expiresAt > Date.now() + 60_000) return cached.token;
  const email = env("OWNER_EMAIL");
  const password = env("OWNER_PASSWORD");
  if (!email || !password) throw new Error("伺服器缺少 OWNER_EMAIL / OWNER_PASSWORD");
  const r = await fetch(`${url}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: anonKey, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`Supabase 登入失敗(${r.status})`);
  const j = (await r.json()) as { access_token: string; expires_in: number };
  cached = { token: j.access_token, expiresAt: Date.now() + j.expires_in * 1000 };
  return cached.token;
}

/** 以 owner 身分呼叫 PostgREST */
export async function rest(path: string, init: { method?: string; body?: unknown; prefer?: string } = {}): Promise<unknown> {
  const url = env("SUPABASE_URL", "VITE_SUPABASE_URL");
  const anonKey = env("SUPABASE_PUBLISHABLE_KEY", "VITE_SUPABASE_ANON_KEY");
  if (!url || !anonKey) throw new Error("伺服器缺少 Supabase 設定");
  const token = await ownerToken(url, anonKey);
  const r = await fetch(`${url}/rest/v1/${path}`, {
    method: init.method ?? "GET",
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.prefer ? { Prefer: init.prefer } : {}),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (!r.ok) throw new Error(`資料庫錯誤(${r.status})`);
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}
