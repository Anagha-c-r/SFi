import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Empty, EnvTag, Notice, PageHeader, Spinner, useLoad } from "../components/ui";
import { fmtDate } from "../format";
import type { Institution } from "../types";

type Row = Institution & { submission_count: number; user_count: number };

const CATEGORIES: Record<string, string> = {
  commercial_bank: "Commercial bank",
  microfinance_bank: "Microfinance bank",
  credit_reference_bureau: "Credit reference bureau",
  money_remittance_provider: "Money remittance provider",
  forex_bureau: "Forex bureau",
  other: "Other",
};

export function AdminInstitutions() {
  const { can } = useAuth();
  const { data, error, reload } = useLoad(() => api.get<Row[]>("/api/admin/institutions"), []);
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (!can("platform_admin")) return <Notice tone="bad">Only Finoworks platform admins can see this page.</Notice>;
  if (error) return <Notice tone="bad">{error}</Notice>;
  if (!data) return <Spinner />;

  async function toggle(i: Row) {
    if (i.is_active && !window.confirm(`Disable ${i.name}? Its users won't be able to sign in.`)) return;
    await api.patch(`/api/admin/institutions/${i.id}`, { is_active: !i.is_active });
    reload();
  }

  return (
    <>
      <PageHeader
        title="Institutions"
        sub="Banks and other reporting institutions using the portal."
        actions={!adding && <button className="btn btn-primary" onClick={() => setAdding(true)}>Onboard an institution</button>}
      />
      {msg && <Notice tone="good">{msg}</Notice>}
      {adding && <AddInstitution onCancel={() => setAdding(false)} onDone={(m) => { setAdding(false); setMsg(m); reload(); }} />}
      {data.length === 0 ? (
        <Empty title="No institutions yet.">Onboard the first one to give its team access.</Empty>
      ) : (
        <section className="panel flush">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Institution</th>
                  <th>Type</th>
                  <th>Environment</th>
                  <th className="num">Users</th>
                  <th className="num">Uploads</th>
                  <th>Since</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((i) => (
                  <tr key={i.id} className={i.is_active ? "" : "row-off"}>
                    <td>
                      {i.name} {!i.is_active && <Badge>Disabled</Badge>}
                      <div className="muted small">CBK code {i.institution_code}</div>
                    </td>
                    <td>{CATEGORIES[i.category] ?? i.category}</td>
                    <td>
                      <EnvTag env={i.environment} /> {!i.has_credentials && <Badge tone="warn">No credentials</Badge>}
                    </td>
                    <td className="num">{i.user_count}</td>
                    <td className="num">{i.submission_count}</td>
                    <td className="small">{fmtDate(i.created_at)}</td>
                    <td className="right">
                      <button className="btn btn-quiet" onClick={() => toggle(i)}>
                        {i.is_active ? "Disable" : "Enable"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

function AddInstitution({ onDone, onCancel }: { onDone: (m: string) => void; onCancel: () => void }) {
  const [f, setF] = useState({
    name: "",
    institution_code: "",
    category: "commercial_bank",
    environment: "uat",
    admin_full_name: "",
    admin_email: "",
    admin_password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/admin/institutions", f);
      onDone(`${f.name} is set up. ${f.admin_full_name} can sign in with ${f.admin_email} and add the CBK credentials.`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="panel form-narrow" onSubmit={submit}>
      <h2>Onboard an institution</h2>
      {error && <Notice tone="bad">{error}</Notice>}
      <label className="field">
        <span>Institution name</span>
        <input required value={f.name} onChange={set("name")} />
      </label>
      <label className="field">
        <span>CBK institution code</span>
        <input required value={f.institution_code} onChange={set("institution_code")} placeholder="e.g. 0000001" />
      </label>
      <label className="field">
        <span>Type</span>
        <select value={f.category} onChange={set("category")}>
          {Object.entries(CATEGORIES).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Start in</span>
        <select value={f.environment} onChange={set("environment")}>
          <option value="uat">UAT (recommended until testing is signed off)</option>
          <option value="prod">Production</option>
        </select>
      </label>
      <h2 className="mt">First administrator</h2>
      <label className="field">
        <span>Full name</span>
        <input required value={f.admin_full_name} onChange={set("admin_full_name")} />
      </label>
      <label className="field">
        <span>Work email</span>
        <input type="email" required value={f.admin_email} onChange={set("admin_email")} />
      </label>
      <label className="field">
        <span>Temporary password</span>
        <input required minLength={10} value={f.admin_password} onChange={set("admin_password")} autoComplete="off" />
      </label>
      <div className="actions">
        <button className="btn btn-primary">Onboard institution</button>
        <button type="button" className="btn btn-quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
