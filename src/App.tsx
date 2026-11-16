import { useCallback, useEffect, useRef, useState } from "react";
import type { AppState, DraftAnswer, ErrorType, QuestionMeta, ResultItem } from "./types";
import type { Backend } from "./backend/types";
import { createBackend } from "./backend";
import { todayStr } from "./lib/date";
import { buildSession } from "./lib/buildSession";
import { Quiz } from "./components/Quiz";
import { Results } from "./components/Results";
import { Insights } from "./components/Insights";
import { Plan } from "./components/Plan";
import { Settings } from "./components/Settings";
import { Login } from "./components/Login";

type Tab = "quiz" | "plan" | "wrong" | "settings";
const TAB_PATH: Record<Tab, string> = { quiz: "/quiz", plan: "/plan", wrong: "/wrong", settings: "/settings" };
const TAB_LABEL: Record<Tab, string> = { quiz: "今日測驗", plan: "讀書計畫", wrong: "錯題與弱點", settings: "設定" };

/** 通知連結 /quiz 直接進當天測驗;/ 也是測驗 */
const tabFromPath = (): Tab =>
  (Object.entries(TAB_PATH).find(([, p]) => window.location.pathname.startsWith(p))?.[0] as Tab | undefined) ?? "quiz";

type Boot = "loading" | "login" | "ready" | "fatal";

export function App() {
  const [backend, setBackend] = useState<Backend | null>(null);
  const [boot, setBoot] = useState<Boot>("loading");
  const [fatal, setFatal] = useState("");
  const [user, setUser] = useState("");
  const [today, setToday] = useState(todayStr);
  const [questions, setQuestions] = useState<Map<string, QuestionMeta>>(new Map());
  const [state, setState] = useState<AppState | null>(null);
  const [results, setResults] = useState<ResultItem[] | null>(null);
  const [tab, setTab] = useState<Tab>(tabFromPath);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const stateRef = useRef<AppState | null>(null);
  stateRef.current = state;
  const saveTimer = useRef<number | undefined>(undefined);

  const run = useCallback(async (fn: () => Promise<void>) => {
    try {
      setError("");
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "發生錯誤");
    }
  }, []);

  /** 載入題庫與資料;今天還沒有測驗就產生五題並存起來 */
  const loadAll = useCallback(async (be: Backend, day: string) => {
    const qs = await be.loadQuestions();
    const qmap = new Map(qs.map((q) => [q.id, q]));
    let st = await be.loadState(day);
    if (!st.sessions.some((s) => s.date === day)) {
      await be.createSession(buildSession(day, qs, st));
      st = await be.loadState(day);
    }
    const session = st.sessions.find((s) => s.date === day);
    setQuestions(qmap);
    setState(st);
    setResults(session?.submittedAt ? await be.getResults(day) : null);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const be = await createBackend();
        setBackend(be);
        const email = await be.getUser();
        if (!email) return setBoot("login");
        setUser(email);
        await loadAll(be, todayStr());
        setBoot("ready");
      } catch (e) {
        setFatal(e instanceof Error ? e.message : "初始化失敗");
        setBoot("fatal");
      }
    })();
  }, [loadAll]);

  // 跨日後回到 App(例如早上點通知)時,換成當天測驗
  useEffect(() => {
    const onVisible = () => {
      const now = todayStr();
      if (document.visibilityState === "visible" && backend && boot === "ready" && now !== today) {
        setToday(now);
        void run(() => loadAll(backend, now));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [backend, boot, today, loadAll, run]);

  const goTab = (t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", TAB_PATH[t]);
  };

  const session = state?.sessions.find((s) => s.date === today);

  /** 點選答案先更新畫面,稍後(250ms)合併寫回資料庫 */
  const updateDraft = (fn: (d: Record<string, DraftAnswer>) => Record<string, DraftAnswer>) => {
    if (!backend || !stateRef.current || !session) return;
    const next = fn(session.draft);
    setState({
      ...stateRef.current,
      sessions: stateRef.current.sessions.map((s) => (s.date === today ? { ...s, draft: next } : s)),
    });
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void run(() => backend.saveDraft(today, next)), 250);
  };

  const submit = () =>
    run(async () => {
      if (!backend || !session) return;
      setBusy(true);
      try {
        window.clearTimeout(saveTimer.current);
        await backend.saveDraft(today, session.draft);
        const r = await backend.submit(today);
        setResults(r);
        setState(await backend.loadState(today));
      } finally {
        setBusy(false);
      }
    });

  const afterTaskChange = (fn: () => Promise<void>) =>
    run(async () => {
      if (!backend) return;
      await fn();
      setState(await backend.loadState(today));
    });

  if (boot === "loading") return <div className="app"><main><p className="hint">載入中…</p></main></div>;
  if (boot === "fatal") return <div className="app"><main><div className="card"><p>{fatal}</p></div></main></div>;
  if (boot === "login" && backend) {
    return (
      <div className="app">
        <header><h1>線代每日測驗</h1></header>
        <main>
          <Login
            onSignIn={async (email, password) => {
              await backend.signIn(email, password);
              setUser((await backend.getUser()) ?? email);
              await loadAll(backend, today);
              setBoot("ready");
            }}
          />
        </main>
      </div>
    );
  }
  if (!backend || !state || !session) return null;

  const score = results ? results.filter((r) => r.correct).length : null;

  return (
    <div className="app">
      <header>
        <h1>線代每日測驗</h1>
        <span className="date">{today}</span>
      </header>

      {error && (
        <div className="banner" role="alert" onClick={() => setError("")}>
          {error}(點一下關閉)
        </div>
      )}

      <main>
        {tab === "quiz" &&
          (session.submittedAt && results ? (
            <Results
              session={session}
              questions={questions}
              results={results}
              onErrorType={(id: string, t: ErrorType) =>
                run(async () => {
                  await backend.setErrorType(id, t);
                  setResults((rs) => rs && rs.map((r) => (r.attemptId === id ? { ...r, errorType: t } : r)));
                  setState(await backend.loadState(today));
                })
              }
            />
          ) : (
            <Quiz
              key={today}
              session={session}
              questions={questions}
              busy={busy}
              onSelect={(qid, oid) =>
                updateDraft((d) => ({ ...d, [qid]: { unsure: d[qid]?.unsure ?? false, selected: oid } }))
              }
              onUnsure={(qid, unsure) =>
                updateDraft((d) => ({ ...d, [qid]: { selected: d[qid]?.selected ?? "", unsure } }))
              }
              onSubmit={submit}
            />
          ))}

        {tab === "plan" && (
          <Plan
            today={today}
            tasks={state.tasks}
            session={session}
            score={score}
            onAdd={(t) => afterTaskChange(() => backend.addTask(t))}
            onToggle={(id, done) => afterTaskChange(() => backend.toggleTask(id, done))}
            onDelete={(id) => afterTaskChange(() => backend.deleteTask(id))}
            onGoQuiz={() => goTab("quiz")}
          />
        )}

        {tab === "wrong" && (
          <Insights state={state} questions={questions} today={today} getKey={(id) => backend.getKey(id)} />
        )}

        {tab === "settings" && (
          <Settings
            user={user}
            mode={backend.mode}
            currentChapter={state.settings.currentChapter}
            onChapter={(n) =>
              run(async () => {
                await backend.setChapter(n);
                setState(await backend.loadState(today));
              })
            }
            onSignOut={() => {
              void backend.signOut().then(() => {
                setState(null);
                setBoot("login");
              });
            }}
            onReset={
              backend.reset
                ? () =>
                    run(async () => {
                      await backend.reset!();
                      await loadAll(backend, today);
                    })
                : undefined
            }
          />
        )}
      </main>

      <nav>
        {(Object.keys(TAB_PATH) as Tab[]).map((id) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => goTab(id)}>
            {TAB_LABEL[id]}
          </button>
        ))}
      </nav>
    </div>
  );
}
