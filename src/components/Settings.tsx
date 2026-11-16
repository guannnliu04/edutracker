import { CHAPTERS } from "../data/concepts";

interface Props {
  user: string;
  mode: "supabase" | "local";
  currentChapter: number;
  onChapter: (n: number) => void;
  onSignOut: () => void;
  onReset?: () => void;
}

export function Settings({ user, mode, currentChapter, onChapter, onSignOut, onReset }: Props) {
  return (
    <div className="stack">
      <div className="card">
        <div className="label" style={{ marginTop: 0 }}>目前學習章節(每日 1 題會出自這裡)</div>
        <select value={currentChapter} onChange={(e) => onChapter(Number(e.target.value))}>
          {Object.entries(CHAPTERS).map(([n, name]) => (
            <option key={n} value={n}>第 {n} 章 {name}</option>
          ))}
        </select>
        <p className="hint">更換章節只影響之後新產生的測驗,不會改動今天已經出好的五題。</p>
      </div>
      <div className="card">
        <div className="label" style={{ marginTop: 0 }}>帳號與資料</div>
        <p className="hint" style={{ marginTop: 0 }}>
          {mode === "supabase" ? `已登入:${user}。紀錄存在 Supabase,換手機也在。` : "本機示範模式:紀錄只存在這個瀏覽器。"}
        </p>
        {mode === "supabase" && <button className="btn" onClick={onSignOut}>登出</button>}
        {onReset && (
          <button
            className="btn danger"
            onClick={() => {
              if (window.confirm("確定要清除所有作答紀錄嗎?")) onReset();
            }}
          >
            清除所有紀錄
          </button>
        )}
      </div>
    </div>
  );
}
