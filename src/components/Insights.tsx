import { useState } from "react";
import type { AppState, QuestionMeta } from "../types";
import { ERROR_TYPE_LABEL } from "../types";
import { conceptName } from "../data/concepts";
import { addDays } from "../lib/date";
import { dueReviews } from "../lib/review";
import { conceptStats, weekSummary } from "../lib/weakness";
import { practiceAsAttempts } from "../lib/practice";
import type { QuestionKey } from "../backend/types";
import { MathText } from "./Math";

interface Props {
  state: AppState;
  questions: Map<string, QuestionMeta>;
  today: string;
  getKey: (questionId: string) => Promise<QuestionKey>;
}

export function Insights({ state, questions, today, getKey }: Props) {
  const [keys, setKeys] = useState<Record<string, QuestionKey>>({});
  const [open, setOpen] = useState<string | null>(null);

  // App 內五題 + 你從 ChatGPT 匯入的練習,一起算
  const all = [...state.attempts, ...practiceAsAttempts(state.practice)];
  const total = all.length;
  const rate = total ? Math.round((all.filter((a) => a.correct).length / total) * 100) : 0;
  const due = dueReviews(state.reviews, today).length;
  const week = weekSummary(all, addDays(today, -6));
  const weak = conceptStats(all).slice(0, 10);
  const wrong = state.attempts.filter((a) => !a.correct).sort((a, b) => b.date.localeCompare(a.date));
  const pending = [...state.reviews].sort((a, b) => a.dueDate.localeCompare(b.dueDate));

  const toggle = async (questionId: string, attemptId: string) => {
    setOpen(open === attemptId ? null : attemptId);
    if (!keys[questionId]) {
      try {
        const k = await getKey(questionId);
        setKeys((prev) => ({ ...prev, [questionId]: k }));
      } catch {
        /* 取不到就不顯示解析 */
      }
    }
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="stats">
          <div><b>{total}</b><span>已作答</span></div>
          <div><b>{total ? `${rate}%` : "—"}</b><span>總正確率</span></div>
          <div><b>{due}</b><span>今日到期複習</span></div>
        </div>
      </div>

      <h2>近 7 天</h2>
      <div className="card">
        {week.attempts === 0 ? (
          <p className="hint">這 7 天還沒有作答紀錄。</p>
        ) : (
          <>
            <div className="stats">
              <div><b>{Math.round((week.correct / week.attempts) * 100)}%</b><span>正確率({week.correct}/{week.attempts})</span></div>
              <div><b>{week.unsure}</b><span>勾了不確定</span></div>
            </div>
            {Object.keys(week.byError).length > 0 && (
              <div className="tags" style={{ marginTop: 12 }}>
                {(Object.entries(week.byError) as [keyof typeof ERROR_TYPE_LABEL, number][]).map(([t, n]) => (
                  <span key={t} className="tag muted">{ERROR_TYPE_LABEL[t]} × {n}</span>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <h2>觀念弱點 Top 10</h2>
      <div className="card">
        {weak.length === 0 && <p className="hint">還沒有足夠資料。答錯或勾「不確定」的觀念會出現在這裡。</p>}
        {weak.map((w) => (
          <div key={w.conceptId} className="weak">
            <div className="weakhead">
              <span>{conceptName(w.conceptId)}</span>
              <span className="hint">
                錯 {w.wrong}・不確定 {w.unsureRight}・遺忘 {w.forgot}
              </span>
            </div>
            <div className="bar"><div style={{ width: `${Math.round(w.score * 100)}%` }} /></div>
          </div>
        ))}
        {weak.length > 0 && (
          <p className="hint">弱點分數 =(答錯 + 0.5×答對但不確定)÷ 作答次數。「遺忘」是先答對、後來又答錯的次數。</p>
        )}
      </div>

      <h2>錯題紀錄</h2>
      {wrong.length === 0 && <p className="hint">目前沒有錯題。</p>}
      {wrong.map((a) => {
        const q = questions.get(a.questionId);
        if (!q) return null;
        const key = keys[a.questionId];
        return (
          <div key={a.id} className="card">
            <div className="tags">
              <span className="tag">{a.date}</span>
              <span className="tag">{conceptName(a.conceptId)}</span>
              {a.errorType && <span className="tag muted">{ERROR_TYPE_LABEL[a.errorType]}</span>}
              {a.unsure && <span className="tag muted">不確定</span>}
            </div>
            <p className="prompt small"><MathText text={q.prompt} /></p>
            <button className="btn ghost small" onClick={() => toggle(a.questionId, a.id)}>
              {open === a.id ? "收起解析" : "看解析"}
            </button>
            {open === a.id && key && (
              <div className="explain">
                <div>
                  <b>正解:</b>
                  <MathText text={q.options.find((o) => o.id === key.correctOptionId)?.text ?? ""} />
                </div>
                <div style={{ marginTop: 8 }}><MathText text={key.explanation} /></div>
              </div>
            )}
          </div>
        );
      })}

      {state.practice.some((p) => !p.correct) && (
        <>
          <h2>ChatGPT 練習錯題</h2>
          {[...state.practice]
            .filter((p) => !p.correct)
            .sort((a, b) => b.date.localeCompare(a.date))
            .map((p) => (
              <div key={p.id} className="card">
                <div className="tags">
                  <span className="tag">{p.date}</span>
                  <span className="tag">{conceptName(p.concept)}</span>
                  {p.errorType && <span className="tag muted">{ERROR_TYPE_LABEL[p.errorType]}</span>}
                  {p.unsure && <span className="tag muted">不確定</span>}
                </div>
                <p className="prompt small"><MathText text={p.prompt} /></p>
                <div className="explain">
                  <div>你的答案:{p.myAnswer}　正解:{p.correctAnswer}</div>
                  {p.explanation && <div style={{ marginTop: 8 }}><MathText text={p.explanation} /></div>}
                </div>
              </div>
            ))}
        </>
      )}

      {pending.length > 0 && (
        <>
          <h2>複習排程</h2>
          <div className="card">
            {pending.map((r) => (
              <div key={r.id} className="sched">
                <span>{r.dueDate}{r.dueDate <= today ? "(到期)" : ""}</span>
                <span>{conceptName(r.conceptId)}・第 {r.stage} 日</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
