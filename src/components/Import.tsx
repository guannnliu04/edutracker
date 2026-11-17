import { useState } from "react";
import { PRACTICE_EXAMPLE, parsePracticeRecord } from "../../shared/practice";

interface Props {
  today: string;
  onImport: (json: unknown) => Promise<number>;
}

export function Import({ today, onImport }: Props) {
  const [text, setText] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setMsg(null);
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      return setMsg({ ok: false, text: "這不是有效的 JSON。請完整複製 GPT 給你的那一整段(含最外層的 { })。" });
    }
    const parsed = parsePracticeRecord(json, today);
    if (!parsed.ok) return setMsg({ ok: false, text: parsed.error });
    setBusy(true);
    try {
      const n = await onImport(json);
      const skipped = parsed.logs.length - n;
      setMsg({ ok: true, text: `已匯入 ${n} 題${skipped > 0 ? `(${skipped} 題先前已匯入過,已略過)` : ""}。到「弱點」頁查看。` });
      setText("");
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "匯入失敗" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="label" style={{ marginTop: 0 }}>貼上 GPT 的練習紀錄</div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='{"items":[ ... ]}'
          rows={10}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
        />
        {msg && <p className={`hint ${msg.ok ? "" : "err"}`}>{msg.text}</p>}
        <button className="btn primary" disabled={busy || !text.trim()} onClick={submit}>
          {busy ? "匯入中…" : "驗證並匯入"}
        </button>
        <p className="hint">格式不合會整批退回並告訴你哪一題哪個欄位有問題,不會只存一半。同一天同一題重複貼上不會重複計算。</p>
      </div>
      <details className="card">
        <summary>格式範例(給 GPT 看的)</summary>
        <pre>{JSON.stringify(PRACTICE_EXAMPLE, null, 2)}</pre>
      </details>
    </div>
  );
}
