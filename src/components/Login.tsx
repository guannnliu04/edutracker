import { useState } from "react";

export function Login({ onSignIn }: { onSignIn: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <form
      className="card form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          await onSignIn(email.trim(), password);
        } catch (err) {
          setError(err instanceof Error ? err.message : "登入失敗");
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="label" style={{ marginTop: 0 }}>登入</div>
      <input type="email" autoComplete="username" inputMode="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <input type="password" autoComplete="current-password" placeholder="密碼" value={password} onChange={(e) => setPassword(e.target.value)} required />
      {error && <p className="hint err">{error}</p>}
      <button className="btn primary" type="submit" disabled={busy}>{busy ? "登入中…" : "登入"}</button>
      <p className="hint">這是個人使用的系統,帳號由管理者在 Supabase 後台建立。</p>
    </form>
  );
}
