import type { AppState } from "../types";
import { ERROR_TYPE_LABEL } from "../types";
import { conceptName } from "../data/concepts";
import { getQuestion } from "../lib/session";
import { dueReviews } from "../lib/review";
import { MathText } from "./Math";

export function WrongBook({ state, today }: { state: AppState; today: string }) {
  const wrong = state.attempts.filter((a) => !a.correct).sort((a, b) => b.date.localeCompare(a.date));
  const pending = state.reviews.filter((r) => !r.done).sort((a, b) => a.dueDate.localeCompare(b.dueDate));
  const due = dueReviews(state.reviews, today).length;
  const total = state.attempts.length;
  const rate = total ? Math.round((state.attempts.filter((a) => a.correct).length / total) * 100) : 0;

  return (
    <div className="stack">
      <div className="card">
        <div className="stats">
          <div><b>{total}</b><span>已作答</span></div>
          <div><b>{total ? `${rate}%` : "—"}</b><span>正確率</span></div>
          <div><b>{due}</b><span>今日到期複習</span></div>
        </div>
      </div>

      <h2>錯題紀錄</h2>
      {wrong.length === 0 && <p className="hint">目前沒有錯題。</p>}
      {wrong.map((a) => {
        const q = getQuestion(a.questionId);
        return (
          <div key={a.id} className="card">
            <div className="tags">
              <span className="tag">{a.date}</span>
              <span className="tag">{conceptName(a.conceptId)}</span>
              {a.errorType && <span className="tag muted">{ERROR_TYPE_LABEL[a.errorType]}</span>}
              {a.unsure && <span className="tag muted">不確定</span>}
            </div>
            <p className="prompt small"><MathText text={q.prompt} /></p>
          </div>
        );
      })}

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
