import { useState } from "react";
import type { DailySession, StudyTask } from "../types";

interface Props {
  today: string;
  tasks: StudyTask[];
  session: DailySession;
  score: number | null;
  onAdd: (t: Pick<StudyTask, "date" | "title" | "subject" | "minutes">) => void;
  onToggle: (id: string, done: boolean) => void;
  onDelete: (id: string) => void;
  onGoQuiz: () => void;
}

export function Plan({ today, tasks, session, score, onAdd, onToggle, onDelete, onGoQuiz }: Props) {
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("");
  const [subject, setSubject] = useState("");

  const doneCount = tasks.filter((t) => t.done).length;
  const totalMin = tasks.reduce((n, t) => n + t.minutes, 0);
  const doneMin = tasks.filter((t) => t.done).reduce((n, t) => n + t.minutes, 0);
  const answered = session.slots.filter((s) => session.draft[s.questionId]?.selected).length;
  const quizDone = Boolean(session.submittedAt);

  return (
    <div className="stack">
      <div className="card">
        <div className="label" style={{ marginTop: 0 }}>今日讀書進度</div>
        <div className="stats">
          <div><b>{doneCount}/{tasks.length}</b><span>項目完成</span></div>
          <div><b>{doneMin}/{totalMin}</b><span>分鐘</span></div>
        </div>
        <div className="bar big">
          <div style={{ width: tasks.length ? `${Math.round((doneCount / tasks.length) * 100)}%` : "0%" }} />
        </div>
      </div>

      <div className="card">
        <div className="label" style={{ marginTop: 0 }}>線代五題測驗</div>
        <div className="sched" style={{ border: 0 }}>
          <span>
            {quizDone
              ? `已完成:${score ?? "?"} / ${session.slots.length}`
              : answered > 0
                ? `進行中:已答 ${answered} / ${session.slots.length}`
                : "尚未開始"}
          </span>
          <button className="btn small" onClick={onGoQuiz}>{quizDone ? "看解析" : answered > 0 ? "繼續" : "開始"}</button>
        </div>
      </div>

      <h2>今日計畫</h2>
      <div className="card">
        {tasks.length === 0 && <p className="hint">今天還沒有讀書項目,從下面新增。</p>}
        {tasks.map((t) => (
          <div key={t.id} className={`task ${t.done ? "done" : ""}`}>
            <label>
              <input type="checkbox" checked={t.done} onChange={(e) => onToggle(t.id, e.target.checked)} />
              <span>
                {t.title}
                <small>{[t.subject, t.minutes ? `${t.minutes} 分` : ""].filter(Boolean).join("・")}</small>
              </span>
            </label>
            <button className="x" aria-label={`刪除 ${t.title}`} onClick={() => onDelete(t.id)}>✕</button>
          </div>
        ))}
      </div>

      <form
        className="card form"
        onSubmit={(e) => {
          e.preventDefault();
          const t = title.trim();
          if (!t) return;
          onAdd({ date: today, title: t, subject: subject.trim(), minutes: Math.max(0, Math.min(1440, Number(minutes) || 0)) });
          setTitle("");
          setMinutes("");
        }}
      >
        <div className="label" style={{ marginTop: 0 }}>新增項目</div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如:線代第 7 章習題" maxLength={200} />
        <div className="row">
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="科目(選填)" maxLength={50} />
          <input value={minutes} onChange={(e) => setMinutes(e.target.value)} placeholder="分鐘" inputMode="numeric" />
        </div>
        <button className="btn primary" type="submit" disabled={!title.trim()}>新增</button>
      </form>
    </div>
  );
}
