import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import record from "./record";
import context from "./context";
import { checkBearer, todayInTz } from "../_lib";

const KEY = "k".repeat(32);

function mockRes() {
  const out = { code: 0, body: undefined as unknown, headers: {} as Record<string, string> };
  const res = {
    status(c: number) { out.code = c; return res; },
    setHeader(n: string, v: string) { out.headers[n] = v; return res; },
    json(b: unknown) { out.body = b; },
  };
  return { res, out };
}
const authed = { authorization: `Bearer ${KEY}` };
const body = { items: [{ concept: "eigen-basic", prompt: "p", myAnswer: "C", correctAnswer: "B", correct: false }] };

let calls: { url: string; init?: RequestInit }[];
function fakeSupabase(handlers: Record<string, () => unknown>) {
  calls = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const key = Object.keys(handlers).find((k) => url.includes(k));
    if (!key) return new Response("{}", { status: 404 });
    return new Response(JSON.stringify(handlers[key]()), { status: 200 });
  });
}

beforeEach(() => {
  vi.stubEnv("GPT_API_KEY", KEY);
  vi.stubEnv("SUPABASE_URL", "https://x.supabase.co");
  vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test");
  vi.stubEnv("OWNER_EMAIL", "me@example.com");
  vi.stubEnv("OWNER_PASSWORD", "pw");
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("金鑰驗證", () => {
  it("正確的 Bearer 通過;錯的、空的、沒設定的都拒絕", () => {
    expect(checkBearer({ headers: authed }, KEY)).toBe(true);
    expect(checkBearer({ headers: { authorization: "Bearer wrong" } }, KEY)).toBe(false);
    expect(checkBearer({ headers: {} }, KEY)).toBe(false);
    expect(checkBearer({ headers: { authorization: "Bearer " } }, "")).toBe(false);
    expect(checkBearer({ headers: { authorization: "Bearer short" } }, "short")).toBe(false); // 金鑰太短視為未設定
  });
  it("日期以台北時區計算(UTC 前一天 20:00 = 台北當天 04:00)", () => {
    expect(todayInTz("Asia/Taipei", new Date("2026-11-17T20:00:00Z"))).toBe("2026-11-18");
  });
});

describe("POST /api/gpt/record", () => {
  it("沒金鑰 → 401,而且完全不碰資料庫", async () => {
    fakeSupabase({});
    const { res, out } = mockRes();
    await record({ method: "POST", headers: {}, body }, res);
    expect(out.code).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it("非 POST → 405", async () => {
    const { res, out } = mockRes();
    await record({ method: "GET", headers: authed }, res);
    expect(out.code).toBe(405);
  });

  it("格式錯誤 → 400,說明哪題哪欄,不碰資料庫", async () => {
    fakeSupabase({});
    const { res, out } = mockRes();
    await record({ method: "POST", headers: authed, body: { items: [{ concept: "x" }] } }, res);
    expect(out.code).toBe(400);
    expect((out.body as { error: string }).error).toMatch(/第 1 題/);
    expect(calls).toHaveLength(0);
  });

  it("成功:以 owner 身分寫入,回傳筆數,回應不含機密", async () => {
    fakeSupabase({
      "/auth/v1/token": () => ({ access_token: "jwt-abc", expires_in: 3600 }),
      "/rest/v1/practice_logs": () => [{ id: "1" }],
    });
    const { res, out } = mockRes();
    await record({ method: "POST", headers: authed, body }, res);
    expect(out.code).toBe(200);
    expect(out.body).toEqual({ saved: 1, duplicatesSkipped: 0 });
    const write = calls.find((c) => c.url.includes("/rest/v1/practice_logs"))!;
    expect((write.init!.headers as Record<string, string>).Authorization).toBe("Bearer jwt-abc");
    expect(write.url).toContain("on_conflict=user_id,date,prompt_hash");
    expect(JSON.stringify(out.body)).not.toMatch(/pw|jwt-abc|me@example/);
  });

  it("資料庫失敗 → 502,不外洩內部細節", async () => {
    fakeSupabase({ "/auth/v1/token": () => ({ access_token: "t", expires_in: 3600 }) });
    const { res, out } = mockRes();
    await record({ method: "POST", headers: authed, body }, res);
    expect(out.code).toBe(502);
    expect(JSON.stringify(out.body)).not.toMatch(/supabase|404/);
  });
});

describe("GET /api/gpt/context", () => {
  it("沒金鑰 → 401", async () => {
    const { res, out } = mockRes();
    await context({ method: "GET", headers: {} }, res);
    expect(out.code).toBe(401);
  });

  it("合併 GPT 練習與 App 作答,回傳弱點與待複習", async () => {
    fakeSupabase({
      "/auth/v1/token": () => ({ access_token: "t", expires_in: 3600 }),
      "practice_logs": () => [{ date: "2026-11-01", concept: "eigen-basic", correct: false, unsure: false, error_type: null, prompt: "p", my_answer: "C", correct_answer: "B" }],
      "attempts": () => [{ date: "2026-11-02", concept_id: "inverse", correct: true, unsure: true, error_type: null }],
    });
    const { res, out } = mockRes();
    await context({ method: "GET", headers: authed }, res);
    expect(out.code).toBe(200);
    const b = out.body as { weakConcepts: { concept: string }[]; summary: { totalAnswered: number } };
    expect(b.summary.totalAnswered).toBe(2);
    expect(b.weakConcepts.map((w) => w.concept).sort()).toEqual(["eigen-basic", "inverse"]);
  });
});
