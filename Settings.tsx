import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Notice, PageHeader, Spinner, useLoad } from "../components/ui";
import type { Institution } from "../types";

const DATE_FORMATS = [
  { value: "%d-%b-%Y", label: "03-Jun-2020 (as the guide specifies)" },
  { value: "%Y-%m-%d", label: "2020-06-03" },
  { value: "%d/%m/%Y", label: "03/06/2020" },
  { value: "%m/%d/%Y", label: "06/03/2020" },
];

export function SettingsPage() {
  const { refresh } = useAuth();
  const { data, error, reload } = useLoad(() => api.get<Institution>("/api/institution"), []);
  const [form, setForm] = useState({
    environment: "uat",
    cbk_client_id: "",
    cbk_client_secret: "",
    cbk_scope: "",
    notification_email: "",
    four_eyes: true,
    date_format: "%d-%b-%Y",
  });
  const [msg, setMsg] = useState<{ tone: "good" | "bad"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data)
      setForm({
        environment: data.environment,
        cbk_client_id: data.cbk_client_id ?? "",
        cbk_client_secret: "",
        cbk_scope: data.cbk_scope ?? "",
        notification_email: data.notification_email ?? "",
        four_eyes: data.four_eyes,
        date_format: data.date_format,
      });
  }, [data]);

  if (error) return <Notice tone="bad">{error}</Notice>;
  if (!data) return <Spinner />;

  async function save(e: FormEvent) {
    e.preventDefault();
    if (form.environment === "prod" && data!.environment !== "prod" &&
        !window.confirm("Switch to CBK production? Approved submissions will be filed for real.")) return;
    setBusy(true);
    setMsg(null);
    const body: Record<string, unknown> = { ...form };
    if (!form.cbk_client_secret) delete body.cbk_client_secret;
    try {
      await api.put("/api/institution/settings", body);
      setMsg({ tone: "good", text: "Settings saved." });
      setForm((f) => ({ ...f, cbk_client_secret: "" }));
      reload();
      void refresh();
    } catch (err) {
      setMsg({ tone: "bad", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<{ ok: boolean; message: string }>("/api/institution/test-connection");
      setMsg({ tone: r.ok ? "good" : "bad", text: r.message });
    } catch (err) {
      setMsg({ tone: "bad", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <PageHeader title="CBK connection" sub={`${data.name}, CBK institution code ${data.institution_code}`} />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <form className="panel form-narrow" onSubmit={save}>
        <h2>API credentials</h2>
        <p className="muted small">
          CBK issues a client ID and secret to each institution. The secret is encrypted when saved and is never shown again.
        </p>
        <fieldset className="field">
          <legend>Environment</legend>
          <div className="radio-row">
            <label className="radio">
              <input type="radio" name="env" checked={form.environment === "uat"} onChange={() => setForm({ ...form, environment: "uat" })} />
              <span>
                <strong>UAT</strong> <span className="muted small">CBK's test environment (preprod)</span>
              </span>
            </label>
            <label className="radio">
              <input type="radio" name="env" checked={form.environment === "prod"} onChange={() => setForm({ ...form, environment: "prod" })} />
              <span>
                <strong>Production</strong> <span className="muted small">Real filings</span>
              </span>
            </label>
          </div>
        </fieldset>
        <label className="field">
          <span>Client ID</span>
          <input value={form.cbk_client_id} onChange={set("cbk_client_id")} autoComplete="off" />
        </label>
        <label className="field">
          <span>
            Client secret {data.has_credentials && <Badge tone="good">Saved</Badge>}
          </span>
          <input
            type="password"
            value={form.cbk_client_secret}
            onChange={set("cbk_client_secret")}
            placeholder={data.has_credentials ? "Leave blank to keep the saved secret" : ""}
            autoComplete="new-password"
          />
        </label>
        <label className="field">
          <span>Scope (optional)</span>
          <input value={form.cbk_scope} onChange={set("cbk_scope")} placeholder="Only if CBK gave you one" />
        </label>

        <h2 className="mt">Submission rules</h2>
        <label className="check">
          <input type="checkbox" checked={form.four_eyes} onChange={(e) => setForm({ ...form, four_eyes: e.target.checked })} />
          <span>
            Four-eyes approval
            <small className="muted"> The person who uploads a file can't approve it.</small>
          </span>
        </label>
        <label className="field">
          <span>Date format sent to CBK</span>
          <select value={form.date_format} onChange={set("date_format")}>
            {DATE_FORMATS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
          <small className="muted">The guide says DD-MMM-YYYY but its samples use other formats. Confirm with CBK.</small>
        </label>
        <label className="field">
          <span>Reporting team email</span>
          <input type="email" value={form.notification_email} onChange={set("notification_email")} />
          <small className="muted">For your records: CBK emails validation results to the address registered with them.</small>
        </label>
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            Save settings
          </button>
          <button type="button" className="btn" disabled={busy || !data.has_credentials} onClick={test}>
            Test connection
          </button>
        </div>
      </form>
    </>
  );
}
