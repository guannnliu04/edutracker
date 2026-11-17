import { checkBearer, env, rest, todayInTz, type Req, type Res } from "../_lib.js";
import { buildContext, type LogRow } from "../../shared/context.js";

interface PracticeRow {
  date: string;
  concept: string;
  correct: boolean;
  unsure: boolean;
  error_type: string | null;
  prompt: string;
  my_answer: string;
  correct_answer: string;
}
interface AttemptRow {
  date: string;
  concept_id: string;
  correct: boolean;
  unsure: boolean;
  error_type: string | null;
}

/** GET /api/gpt/context — GPT 出題前先看:今天該複習什麼、弱點在哪、最近錯了什麼 */
export default async function handler(req: Req, res: Res): Promise<void> {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") return void res.status(405).json({ error: "只接受 GET" });
  if (!checkBearer(req, env("GPT_API_KEY"))) return void res.status(401).json({ error: "金鑰錯誤" });

  try {
    const [practice, attempts] = (await Promise.all([
      rest("practice_logs?select=date,concept,correct,unsure,error_type,prompt,my_answer,correct_answer&order=date.desc&limit=500"),
      rest("attempts?select=date,concept_id,correct,unsure,error_type&order=date.desc&limit=500"),
    ])) as [PracticeRow[], AttemptRow[]];

    const rows: LogRow[] = [
      ...practice.map((p): LogRow => ({
        date: p.date,
        concept: p.concept,
        correct: p.correct,
        unsure: p.unsure,
        errorType: p.error_type ?? undefined,
        prompt: p.prompt,
        myAnswer: p.my_answer,
        correctAnswer: p.correct_answer,
      })),
      ...attempts.map((a): LogRow => ({
        date: a.date,
        concept: a.concept_id,
        correct: a.correct,
        unsure: a.unsure,
        errorType: a.error_type ?? undefined,
      })),
    ];
    res.status(200).json(buildContext(rows, todayInTz()));
  } catch (e) {
    console.error(e);
    res.status(502).json({ error: "讀取失敗,請稍後再試" });
  }
}
