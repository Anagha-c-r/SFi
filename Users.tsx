import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Notice, PageHeader, Spinner, useLoad } from "../components/ui";
import { fmtDateTime, ROLE_HELP, ROLE_LABEL } from "../format";
import type { Role, User } from "../types";

const ROLES = Object.keys(ROLE_HELP) as Exclude<Role, "platform_admin">[];

export function Users() {
  const { user: me } = useAuth();
  const { data, error, reload } = useLoad(() => api.get<User[]>("/api/institution/users"), []);
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState<{ tone: "good" | "bad"; text: string } | null>(null);

  async function update(u: User, change: Partial<{ role: Role; is_active: boolean; password: string }>, done: string) {
    setMsg(null);
    try {
      await api.patch(`/api/institution/users/${u.id}`, change);
      setMsg({ tone: "good", text: done });
      reload();
    } catch (e) {
      setMsg({ tone: "bad", text: (e as Error).message });
    }
  }

  if (error) return <Notice tone="bad">{error}</Notice>;
  if (!data) return <Spinner />;

  return (
    <>
      <PageHeader
        title="Users"
        sub="Everyone at your institution who can use the portal."
        actions={!adding && <button className="btn btn-primary" onClick={() => setAdding(true)}>Add a user</button>}
      />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      {adding && <AddUser onDone={(text) => { setAdding(false); setMsg({ tone: "good", text }); reload(); }} onCancel={() => setAdding(false)} />}

      <section className="panel flush">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Last sign-in</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((u) => (
                <tr key={u.id} className={u.is_active ? "" : "row-off"}>
                  <td>
                    {u.full_name} {!u.is_active && <Badge>Deactivated</Badge>}
                    <div className="muted small">{u.email}</div>
                  </td>
                  <td>
                    <select
                      value={u.role}
                      disabled={u.id === me?.id}
                      aria-label={`Role for ${u.full_name}`}
                      onChange={(e) => update(u, { role: e.target.value as Role }, `${u.full_name} is now ${ROLE_LABEL[e.target.value as Role]}.`)}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABEL[r]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="small">{fmtDateTime(u.last_login_at)}</td>
                  <td className="right">
                    {u.id !== me?.id && (
                      <>
                        <button
                          className="btn btn-quiet"
                          onClick={() => {
                            const p = window.prompt(`New password for ${u.full_name} (10+ characters, mixed case, a number):`);
                            if (p) void update(u, { password: p }, `Password reset for ${u.full_name}.`);
                          }}
                        >
                          Reset password
                        </button>
                        <button
                          className="btn btn-quiet"
                          onClick={() => update(u, { is_active: !u.is_active }, `${u.full_name} ${u.is_active ? "deactivated" : "reactivated"}.`)}
                        >
                          {u.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <h2>What each role can do</h2>
        <dl className="kv">
          {ROLES.map((r) => (
            <div key={r} className="kv-row">
              <dt>{ROLE_LABEL[r]}</dt>
              <dd>{ROLE_HELP[r]}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}

function AddUser({ onDone, onCancel }: { onDone: (msg: string) => void; onCancel: () => void }) {
  const [f, setF] = useState({ full_name: "", email: "", role: "maker", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/institution/users", f);
      onDone(`${f.full_name} can now sign in with ${f.email}. Share the password with them securely.`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="panel form-narrow" onSubmit={submit}>
      <h2>Add a user</h2>
      {error && <Notice tone="bad">{error}</Notice>}
      <label className="field">
        <span>Full name</span>
        <input required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
      </label>
      <label className="field">
        <span>Work email</span>
        <input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
      </label>
      <label className="field">
        <span>Role</span>
        <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r]}: {ROLE_HELP[r]}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Temporary password</span>
        <input type="text" required minLength={10} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="off" />
        <small className="muted">At least 10 characters, with upper- and lower-case letters and a number.</small>
      </label>
      <div className="actions">
        <button className="btn btn-primary" disabled={busy}>Add user</button>
        <button type="button" className="btn btn-quiet" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
