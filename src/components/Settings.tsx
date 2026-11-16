import { CHAPTERS } from "../data/concepts";

interface Props {
  currentChapter: number;
  onChapter: (n: number) => void;
  onReset: () => void;
}

export function Settings({ currentChapter, onChapter, onReset }: Props) {
  return (
    <div className="stack">
      <div className="card">
        <div className="label">目前學習章節(每日 1 題會出自這裡)</div>
        <select value={currentChapter} onChange={(e) => onChapter(Number(e.target.value))}>
          {Object.entries(CHAPTERS).map(([n, name]) => (
            <option key={n} value={n}>第 {n} 章 {name}</option>
          ))}
        </select>
        <p className="hint">更換章節只影響之後新產生的測驗,不會改動今天已經出好的五題。</p>
      </div>
      <div className="card">
        <div className="label">資料</div>
        <p className="hint">第一階段的紀錄只存在這支手機的瀏覽器裡;清除網站資料會一併消失。第二階段會改存 Supabase。</p>
        <button
          className="btn danger"
          onClick={() => {
            if (window.confirm("確定要清除所有作答紀錄嗎?")) onReset();
          }}
        >
          清除所有紀錄
        </button>
      </div>
    </div>
  );
}
