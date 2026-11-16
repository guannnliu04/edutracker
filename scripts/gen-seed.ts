// 由 src/data/questions.ts 產生 supabase/seed.sql(題目 + 伺服器端才讀得到的答案)
// 執行:npm run gen:seed
import { writeFileSync } from "node:fs";
import { QUESTIONS } from "../src/data/questions";

const str = (s: string) => `'${s.replace(/'/g, "''")}'`;
const json = (v: unknown) => `${str(JSON.stringify(v))}::jsonb`;

const lines: string[] = [
  "-- 自動產生,請勿手改:npm run gen:seed",
  "begin;",
  "delete from public.question_keys;",
];
for (const q of QUESTIONS) {
  const options = q.options.map(({ id, text }) => ({ id, text })); // 不含 isCorrect
  lines.push(
    `insert into public.questions (id, kind, chapter, concept_id, prompt, options, origin, source_ref) values (` +
      [str(q.id), str(q.kind), q.chapter, str(q.conceptId), str(q.prompt), json(options), str(q.origin), q.sourceRef ? str(q.sourceRef) : "null"].join(", ") +
      `) on conflict (id) do update set kind = excluded.kind, chapter = excluded.chapter, concept_id = excluded.concept_id, prompt = excluded.prompt, options = excluded.options, origin = excluded.origin, source_ref = excluded.source_ref;`,
  );
}
for (const q of QUESTIONS) {
  const correct = q.options.filter((o) => o.isCorrect);
  if (correct.length !== 1) throw new Error(`${q.id}: 需要恰好一個正確答案`);
  lines.push(
    `insert into public.question_keys (question_id, correct_option_id, explanation) values (${str(q.id)}, ${str(correct[0].id)}, ${str(q.explanation)});`,
  );
}
lines.push("commit;", "");
writeFileSync(new URL("../supabase/seed.sql", import.meta.url), lines.join("\n"));
console.log(`seed.sql: ${QUESTIONS.length} questions`);
