import { checkBearer, env, rest, todayInTz, type Req, type Res } from "../_lib.js";
import { parsePracticeRecord } from "../../shared/practice.js";

/** POST /api/gpt/record — GPT 在你作答完、批改完之後,把這輪練習記進來 */
export default async function handler(req: Req, res: Res): Promise<void> {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return void res.status(405).json({ error: "只接受 POST" });
  if (!checkBearer(req, env("GPT_API_KEY"))) return void res.status(401).json({ error: "金鑰錯誤" });

  const parsed = parsePracticeRecord(req.body, todayInTz());
  if (!parsed.ok) return void res.status(400).json({ error: parsed.error });

  try {
    const rows = parsed.logs.map((l) => ({
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
    const saved = (await rest("practice_logs?on_conflict=user_id,date,prompt_hash", {
      method: "POST",
      body: rows,
      prefer: "resolution=ignore-duplicates,return=representation",
    })) as unknown[] | null;
    const n = saved?.length ?? 0;
    res.status(200).json({ saved: n, duplicatesSkipped: rows.length - n });
  } catch (e) {
    // 不把內部細節(網址、帳號)回給呼叫端
    console.error(e);
    res.status(502).json({ error: "寫入失敗,請稍後再試" });
  }
}
