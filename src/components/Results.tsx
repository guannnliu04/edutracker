import type { AppState, DailySession, ErrorType } from "../types";
import { ERROR_TYPE_LABEL } from "../types";
import { conceptName } from "../data/concepts";
import { getQuestion } from "../lib/session";
import { seededRng, shuffle } from "../lib/rng";
import { MathText } from "./Math";

const LETTERS = ["A", "B", "C", "D"];

interface Props {
  session: DailySession;
  state: AppState;
  onErrorType: (attemptId: string, type: ErrorType) => void;
}

export function Results({ session, state, onErrorType }: Props) {
  const attempts = state.attempts.filter((a) => a.date === session.date);
  const score = attempts.filter((a) => a.correct).length;

  return (
    <div className="stack">
      <div className="card center">
        <div className="score">{score} / {session.slots.length}</div>
        <p className="hint">今天答錯的題目會在 1、3、7 天後以變式再出現。</p>
      </div>

      {session.slots.map((sl, i) => {
        const q = getQuestion(sl.questionId);
        const attempt = attempts.find((a) => a.questionId === q.id);
        if (!attempt) return null;
        const shown = shuffle(q.options, seededRng(`opts:${session.date}:${q.id}`));
        return (
          <div key={q.id} className={`card result ${attempt.correct ? "ok" : "bad"}`}>
            <div className="tags">
              <span className="tag">{i + 1}. {conceptName(q.conceptId)}</span>
              <span className="tag muted">{attempt.correct ? "答對" : "答錯"}</span>
              {attempt.unsure && <span className="tag muted">不確定</span>}
              {q.origin === "self-authored" && <span className="tag muted">自編題</span>}
            </div>
            <p className="prompt"><MathText text={q.prompt} /></p>
            <div className="options">
              {shown.map((o, k) => (
                <div
                  key={o.id}
                  className={`option static ${o.isCorrect ? "correct" : ""} ${attempt.selected === o.id && !o.isCorrect ? "wrong" : ""}`}
                >
                  <span className="letter">{LETTERS[k]}</span>
                  <span><MathText text={o.text} /></span>
                  {o.isCorrect && <b className="mark">正解</b>}
                  {attempt.selected === o.id && <b className="mark">你的答案</b>}
                </div>
              ))}
            </div>
            <div className="explain"><MathText text={q.explanation} /></div>

            {!attempt.correct && (
              <div>
                <div className="label">這題錯在哪?</div>
                <div className="chips">
                  {(Object.keys(ERROR_TYPE_LABEL) as ErrorType[]).map((t) => (
                    <button
                      key={t}
                      className={`chip ${attempt.errorType === t ? "on" : ""}`}
                      onClick={() => onErrorType(attempt.id, t)}
                    >
                      {ERROR_TYPE_LABEL[t]}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
