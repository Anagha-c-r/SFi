import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Notice, PageHeader } from "../components/ui";
import { ROLE_LABEL } from "../format";

export function Account() {
  const { user } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<{ tone: "good" | "bad"; text: string } | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/auth/change-password", { current_password: current, new_password: next });
      setMsg({ tone: "good", text: "Password changed." });
      setCurrent("");
      setNext("");
    } catch (err) {
      setMsg({ tone: "bad", text: (err as Error).message });
    }
  }

  if (!user) return null;
  return (
    <>
      <PageHeader title="Your account" sub={`${user.full_name}, ${user.email}, ${ROLE_LABEL[user.role]}`} />
      <form className="panel form-narrow" onSubmit={submit}>
        <h2>Change password</h2>
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        <label className="field">
          <span>Current password</span>
          <input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </label>
        <label className="field">
          <span>New password</span>
          <input type="password" required minLength={10} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          <small className="muted">At least 10 characters, with upper- and lower-case letters and a number.</small>
        </label>
        <button className="btn btn-primary">Change password</button>
      </form>
    </>
  );
}
