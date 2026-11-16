import { useEffect, useState } from "react";
import type { AppState, ErrorType } from "./types";
import { emptyState, localStorageAdapter } from "./lib/storage";
import { todayStr } from "./lib/date";
import { ensureSession, setErrorType, submitSession, updateSession } from "./lib/session";
import { Quiz } from "./components/Quiz";
import { Results } from "./components/Results";
import { WrongBook } from "./components/WrongBook";
import { Settings } from "./components/Settings";

type Tab = "today" | "wrong" | "settings";

export function App() {
  const [today, setToday] = useState(todayStr);
  const [state, setState] = useState<AppState>(() => ensureSession(localStorageAdapter.load(), todayStr()));
  const [tab, setTab] = useState<Tab>("today");

  useEffect(() => localStorageAdapter.save(state), [state]);

  // 跨日後回到 App(例如早上 8:00 點通知)時,自動換成當天測驗
  useEffect(() => {
    const onVisible = () => {
      const now = todayStr();
      if (now !== today) {
        setToday(now);
        setState((s) => ensureSession(s, now));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [today]);

  const session = state.sessions.find((s) => s.date === today)!;
  const done = Boolean(session.submittedAt);

  return (
    <div className="app">
      <header>
        <h1>線代每日測驗</h1>
        <span className="date">{today}</span>
      </header>

      <main>
        {tab === "today" &&
          (done ? (
            <Results
              session={session}
              state={state}
              onErrorType={(id: string, t: ErrorType) => setState((s) => setErrorType(s, id, t))}
            />
          ) : (
            <Quiz
              key={today}
              session={session}
              onSelect={(qid, oid) =>
                setState((s) =>
                  updateSession(s, today, (x) => ({
                    ...x,
                    draft: { ...x.draft, [qid]: { unsure: x.draft[qid]?.unsure ?? false, selected: oid } },
                  })),
                )
              }
              onUnsure={(qid, unsure) =>
                setState((s) =>
                  updateSession(s, today, (x) => ({
                    ...x,
                    draft: { ...x.draft, [qid]: { selected: x.draft[qid]?.selected ?? "", unsure } },
                  })),
                )
              }
              onSubmit={() => setState((s) => submitSession(s, today, new Date().toISOString()))}
            />
          ))}
        {tab === "wrong" && <WrongBook state={state} today={today} />}
        {tab === "settings" && (
          <Settings
            currentChapter={state.settings.currentChapter}
            onChapter={(n) => setState((s) => ({ ...s, settings: { ...s.settings, currentChapter: n } }))}
            onReset={() => setState(ensureSession(emptyState(), today))}
          />
        )}
      </main>

      <nav>
        {([["today", "今日測驗"], ["wrong", "錯題本"], ["settings", "設定"]] as const).map(([id, label]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}
