// GPT 練習紀錄的格式與驗證。匯入頁(前端)與 /api/gpt/record(伺服器)共用同一份,規則才不會不一致。
// 注意:這個檔案會被 Vercel 函式在 Node ESM 下直接執行,所以只能有「型別匯入」,不可匯入其他執行期模組。

export const ERROR_TYPES = ["concept", "calculation", "careless", "guess"] as const;
export type PracticeErrorType = (typeof ERROR_TYPES)[number];

export interface PracticeInput {
  date: string;
  concept: string;
  prompt: string;
  options?: string[];
  myAnswer: string;
  correctAnswer: string;
  correct: boolean;
  unsure: boolean;
  errorType?: PracticeErrorType;
  explanation?: string;
}

export type ParseResult = { ok: true; logs: PracticeInput[] } | { ok: false; error: string };

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const LETTER_RE = /^[A-D]$/i;

const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

function str(v: unknown, field: string, min: number, max: number): string {
  if (typeof v !== "string") throw new Error(`${field} 必須是文字`);
  const s = v.trim();
  if (s.length < min || s.length > max) throw new Error(`${field} 長度需介於 ${min}~${max} 字`);
  return s;
}

/** 'YYYY-MM-DD' 必須是真實存在的日期,且不能比今天晚超過 1 天(時區誤差) */
function checkDate(d: string, today: string): string {
  if (!DATE_RE.test(d)) throw new Error("date 格式必須是 YYYY-MM-DD");
  const [y, m, day] = d.split("-").map(Number);
  const real = new Date(Date.UTC(y, m - 1, day));
  if (real.getUTCFullYear() !== y || real.getUTCMonth() !== m - 1 || real.getUTCDate() !== day) {
    throw new Error(`date ${d} 不是有效日期`);
  }
  const [ty, tm, td] = today.split("-").map(Number);
  if (real.getTime() > Date.UTC(ty, tm - 1, td) + 86_400_000) throw new Error(`date ${d} 在未來`);
  return d;
}

/**
 * 接受 { date?, items: [...] } 或直接一個陣列。
 * 任何一題不合格就整批退回(回傳第幾題、哪個欄位錯),不會只存一半。
 */
export function parsePracticeRecord(raw: unknown, today: string): ParseResult {
  try {
    const root = Array.isArray(raw) ? { items: raw } : raw;
    if (!isObj(root)) throw new Error("內容必須是 JSON 物件或陣列");
    const items = root.items;
    if (!Array.isArray(items) || items.length < 1 || items.length > 20) {
      throw new Error("items 必須是 1~20 題的陣列");
    }
    const batchDate = root.date === undefined ? today : checkDate(str(root.date, "date", 10, 10), today);

    const logs = items.map((it, i): PracticeInput => {
      const at = `第 ${i + 1} 題`;
      try {
        if (!isObj(it)) throw new Error("必須是物件");
        if (typeof it.correct !== "boolean") throw new Error("correct 必須是 true 或 false");
        const concept = str(it.concept, "concept", 1, 60);
        const prompt = str(it.prompt, "prompt", 1, 2000);
        const myAnswer = str(it.myAnswer, "myAnswer", 1, 500);
        const correctAnswer = str(it.correctAnswer, "correctAnswer", 1, 500);

        // 兩邊都是 A~D 字母時,對錯必須與答案一致,擋掉明顯的 GPT 記錄錯誤
        if (LETTER_RE.test(myAnswer) && LETTER_RE.test(correctAnswer)) {
          const same = myAnswer.toUpperCase() === correctAnswer.toUpperCase();
          if (same !== it.correct) {
            throw new Error(`myAnswer(${myAnswer})與 correctAnswer(${correctAnswer})和 correct=${it.correct} 互相矛盾`);
          }
        }

        let options: string[] | undefined;
        if (it.options !== undefined) {
          if (!Array.isArray(it.options) || it.options.length < 2 || it.options.length > 6) {
            throw new Error("options 必須是 2~6 個選項的陣列");
          }
          options = it.options.map((o, k) => str(o, `options[${k}]`, 1, 500));
        }

        let errorType: PracticeErrorType | undefined;
        if (it.errorType !== undefined && it.errorType !== null) {
          if (!ERROR_TYPES.includes(it.errorType as PracticeErrorType)) {
            throw new Error(`errorType 必須是 ${ERROR_TYPES.join(" / ")}`);
          }
          if (!it.correct) errorType = it.errorType as PracticeErrorType; // 答對的題目不記錯誤類型
        }

        const explanation =
          it.explanation === undefined || it.explanation === null
            ? undefined
            : str(it.explanation, "explanation", 1, 4000);

        return {
          date: it.date === undefined ? batchDate : checkDate(str(it.date, "date", 10, 10), today),
          concept,
          prompt,
          options,
          myAnswer,
          correctAnswer,
          correct: it.correct,
          unsure: it.unsure === true,
          errorType,
          explanation,
        };
      } catch (e) {
        throw new Error(`${at}:${e instanceof Error ? e.message : "格式錯誤"}`);
      }
    });
    return { ok: true, logs };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "格式錯誤" };
  }
}

/** 給匯入頁與 GPT 指令使用的範例 */
export const PRACTICE_EXAMPLE = {
  date: "2026-11-18",
  items: [
    {
      concept: "eigen-basic",
      prompt: "矩陣 [[4,1],[2,3]] 的特徵值為何?",
      options: ["1 與 6", "2 與 5", "3 與 4", "-2 與 -5"],
      myAnswer: "C",
      correctAnswer: "B",
      correct: false,
      unsure: true,
      errorType: "calculation",
      explanation: "tr=7, det=10,λ²-7λ+10=0 → λ=2,5。",
    },
  ],
};
