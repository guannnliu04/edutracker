import type { DailySession, ErrorType, QuestionMeta, ResultItem } from "../types";
import { ERROR_TYPE_LABEL } from "../types";
import { conceptName } from "../data/concepts";
import { seededRng, shuffle } from "../lib/rng";
import { MathText } from "./Math";

const LETTERS = ["A", "B", "C", "D"];

interface Props {
  session: DailySession;
  questions: Map<string, QuestionMeta>;
  results: ResultItem[];
  onErrorType: (attemptId: string, type: ErrorType) => void;
}

export function Results({ session, questions, results, onErrorType }: Props) {
  const score = results.filter((r) => r.correct).length;

  return (
    <div className="stack">
      <div className="card center">
        <div className="score">{score} / {results.length}</div>
        <p className="hint">今天答錯的題目會在 1、3、7 天後以變式再出現。</p>
      </div>

      {results.map((r, i) => {
        const q = questions.get(r.questionId)!;
        const shown = shuffle(q.options, seededRng(`opts:${session.date}:${q.id}`));
        return (
          <div key={r.attemptId} className={`card result ${r.correct ? "ok" : "bad"}`}>
            <div className="tags">
              <span className="tag">{i + 1}. {conceptName(q.conceptId)}</span>
              <span className="tag muted">{r.correct ? "答對" : "答錯"}</span>
              {r.unsure && <span className="tag muted">不確定</span>}
              {q.origin === "self-authored" && <span className="tag muted">自編題</span>}
            </div>
            <p className="prompt"><MathText text={q.prompt} /></p>
            <div className="options">
              {shown.map((o, k) => {
                const isCorrect = o.id === r.correctOptionId;
                const isMine = o.id === r.selected;
                return (
                  <div
                    key={o.id}
                    className={`option static ${isCorrect ? "correct" : ""} ${isMine && !isCorrect ? "wrong" : ""}`}
                  >
                    <span className="letter">{LETTERS[k]}</span>
                    <span><MathText text={o.text} /></span>
                    {isCorrect && <b className="mark">正解</b>}
                    {isMine && <b className="mark">你的答案</b>}
                  </div>
                );
              })}
            </div>
            <div className="explain"><MathText text={r.explanation} /></div>

            {!r.correct && (
              <div>
                <div className="label">這題錯在哪?</div>
                <div className="chips">
                  {(Object.keys(ERROR_TYPE_LABEL) as ErrorType[]).map((t) => (
                    <button
                      key={t}
                      className={`chip ${r.errorType === t ? "on" : ""}`}
                      onClick={() => onErrorType(r.attemptId, t)}
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
