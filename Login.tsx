import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { Notice } from "../components/ui";

export function Login() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-side" aria-hidden>
        <div className="login-ledger">
          {["Card acquiring", "Loan contracts", "Deposit contracts", "FX positions", "Remittances", "Weekly cash"].map((t, i) => (
            <div className="ledger-row" key={t} style={{ animationDelay: `${i * 90}ms` }}>
              <span>{t}</span>
              <span className={i === 3 ? "ledger-wait" : "ledger-ok"}>{i === 3 ? "Awaiting approval" : "Sent to CBK"}</span>
            </div>
          ))}
        </div>
        <p className="login-tag">
          Prepare, check and file your Granular Data Integration returns to the Central Bank of Kenya, with an approver
          on every submission.
        </p>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <h1>Sign in to the GDI Portal</h1>
          <p className="muted">Use the work email your administrator registered.</p>
          {error && <Notice tone="bad">{error}</Notice>}
          <label className="field">
            <span>Email</span>
            <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="fine">Forgot your password? Ask your institution's administrator to reset it.</p>
        </form>
      </section>
    </div>
  );
}
