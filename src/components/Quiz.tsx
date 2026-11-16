import { useMemo, useState } from "react";
import type { DailySession, QuestionMeta } from "../types";
import { seededRng, shuffle } from "../lib/rng";
import { MathText } from "./Math";

const SLOT_LABEL = { review: "舊錯題複習", basic: "基礎觀念", chapter: "最新章節", homework: "作業風格" } as const;
const LETTERS = ["A", "B", "C", "D"];

interface Props {
  session: DailySession;
  questions: Map<string, QuestionMeta>;
  busy: boolean;
  onSelect: (questionId: string, optionId: string) => void;
  onUnsure: (questionId: string, unsure: boolean) => void;
  onSubmit: () => void;
}

export function Quiz({ session, questions, busy, onSelect, onUnsure, onSubmit }: Props) {
  const [index, setIndex] = useState(() => {
    const first = session.slots.findIndex((s) => !session.draft[s.questionId]?.selected);
    return first === -1 ? 0 : first;
  });
  const slot = session.slots[index];
  const question = questions.get(slot.questionId)!;
  const draft = session.draft[question.id];
  const answered = session.slots.filter((s) => session.draft[s.questionId]?.selected).length;
  const allAnswered = answered === session.slots.length;
  const last = index === session.slots.length - 1;

  // 選項順序以「日期+題目」為種子打亂,重新整理後不變
  const options = useMemo(
    () => shuffle(question.options, seededRng(`opts:${session.date}:${question.id}`)),
    [question, session.date],
  );

  return (
    <div className="stack">
      <div className="progress" aria-label={`已作答 ${answered} / ${session.slots.length}`}>
        {session.slots.map((s, i) => (
          <button
            key={s.questionId}
            className={`dot ${i === index ? "current" : ""} ${session.draft[s.questionId]?.selected ? "done" : ""}`}
            onClick={() => setIndex(i)}
            aria-label={`第 ${i + 1} 題`}
          >
            {i + 1}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="tags">
          <span className="tag">{SLOT_LABEL[slot.slot]}</span>
          {question.origin === "self-authored" && <span className="tag muted">自編題</span>}
        </div>
        <p className="prompt"><MathText text={question.prompt} /></p>

        <div className="options" role="radiogroup">
          {options.map((o, i) => (
            <button
              key={o.id}
              role="radio"
              aria-checked={draft?.selected === o.id}
              className={`option ${draft?.selected === o.id ? "selected" : ""}`}
              onClick={() => onSelect(question.id, o.id)}
            >
              <span className="letter">{LETTERS[i]}</span>
              <span><MathText text={o.text} /></span>
            </button>
          ))}
        </div>

        <label className="unsure">
          <input
            type="checkbox"
            checked={draft?.unsure ?? false}
            onChange={(e) => onUnsure(question.id, e.target.checked)}
          />
          不確定
        </label>
      </div>

      <div className="row">
        <button className="btn ghost" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          上一題
        </button>
        {last ? (
          <button className="btn primary" disabled={!allAnswered || busy} onClick={onSubmit}>
            {busy ? "提交中…" : allAnswered ? "提交全部" : `還有 ${session.slots.length - answered} 題未答`}
          </button>
        ) : (
          <button className="btn" onClick={() => setIndex(index + 1)}>下一題</button>
        )}
      </div>
      {!last && allAnswered && (
        <button className="btn primary" disabled={busy} onClick={onSubmit}>
          {busy ? "提交中…" : "提交全部"}
        </button>
      )}
      <p className="hint">五題全部提交後,才會顯示答案與解析。</p>
    </div>
  );
}
