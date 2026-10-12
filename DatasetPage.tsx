import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { Badge, Notice, PageHeader, Spinner, StatusBadge, useLoad } from "../components/ui";
import { fmtDate, timeAgo } from "../format";
import type { DatasetDetail, Page, Submission } from "../types";

export function DatasetPage() {
  const { code = "" } = useParams();
  const { can } = useAuth();
  const ds = useLoad(() => api.get<DatasetDetail>(`/api/datasets/${code}`), [code]);
  const history = useLoad(() => api.get<Page<Submission>>(`/api/submissions?dataset=${code}&page_size=5`), [code]);
  const [showAll, setShowAll] = useState(false);

  if (ds.error) return <Notice tone="bad">{ds.error}</Notice>;
  if (!ds.data) return <Spinner />;
  const d = ds.data;
  const fields = showAll ? d.fields : d.fields.slice(0, 12);

  return (
    <>
      <p className="crumb">
        <Link to="/datasets">Datasets</Link> / {d.group}
      </p>
      <PageHeader
        title={d.title}
        sub={`${d.fields.length} fields per row. Guide section ${d.number}, pages ${d.source_pages[0]}–${d.source_pages[1]}.`}
        actions={
          <button className="btn" onClick={() => download(`/api/datasets/${d.code}/template.csv`, `${d.code}_template.csv`)}>
            Download CSV template
          </button>
        }
      />
      {d.notes && <Notice tone="warn">{d.notes}</Notice>}

      <div className="grid-2 grid-wide-left">
        <section className="panel">
          <h2>Fields</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                  <th>Example</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((f) => (
                  <tr key={f.key}>
                    <td>
                      <div className="field-name">
                        {f.name} {f.required && <Badge tone="info">Required</Badge>}
                      </div>
                      {f.description && <div className="muted small">{f.description}</div>}
                      {f.payload_key !== f.name && <div className="small">Sent to CBK as <code>{f.payload_key}</code></div>}
                    </td>
                    <td>{f.type === "number" ? "Number" : f.type === "date" ? "Date" : "Text"}</td>
                    <td className="mono small">{f.example || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {d.fields.length > 12 && (
            <button className="btn btn-quiet" onClick={() => setShowAll(!showAll)}>
              {showAll ? "Show fewer fields" : `Show all ${d.fields.length} fields`}
            </button>
          )}
          <details className="tech">
            <summary>Technical details</summary>
            <dl className="kv">
              <dt>Endpoint</dt>
              <dd>
                <code>POST {d.endpoint}</code>
              </dd>
              <dt>Rows are sent in</dt>
              <dd>
                <code>{d.array_key}</code>
              </dd>
            </dl>
          </details>
        </section>

        <div className="stack">
          {can("admin", "maker") ? <UploadForm dataset={d} /> : (
            <section className="panel">
              <h2>Upload data</h2>
              <p className="muted">Your role can view submissions but not upload them.</p>
            </section>
          )}
          <section className="panel">
            <h2>Previous uploads</h2>
            {history.data?.items.length ? (
              <ul className="sublist">
                {history.data.items.map((s) => (
                  <li key={s.id}>
                    <Link to={`/submissions/${s.id}`}>
                      <span className="sublist-title">Reporting date {fmtDate(s.reporting_date)}</span>
                      <span className="muted small">
                        {s.row_count.toLocaleString()} rows, {timeAgo(s.created_at)}
                      </span>
                    </Link>
                    <StatusBadge status={s.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Nothing uploaded for this dataset yet.</p>
            )}
            {(history.data?.total ?? 0) > 5 && <Link to={`/submissions?dataset=${d.code}`}>See all {history.data?.total}</Link>}
          </section>
        </div>
      </div>
    </>
  );
}

function UploadForm({ dataset }: { dataset: DatasetDetail }) {
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [reportingDate, setReportingDate] = useState("");
  const [transport, setTransport] = useState("");
  const [overrideId, setOverrideId] = useState("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return setError("Choose a CSV or Excel file to upload.");
    setBusy(true);
    setError(null);
    const fd = new FormData();
    fd.append("dataset_code", dataset.code);
    fd.append("reporting_date", reportingDate);
    fd.append("file", file);
    if (transport) fd.append("transport", transport);
    if (overrideId.trim()) fd.append("override_request_id", overrideId.trim());
    try {
      const sub = await api.post<Submission>("/api/submissions", fd);
      nav(`/submissions/${sub.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Upload data</h2>
      <p className="muted small">
        CSV or Excel (.xlsx), first row as column headers. Column names can match the guide's names or CBK's payload keys.
        The file is checked right away; nothing goes to CBK until an approver signs off.
      </p>
      {error && <Notice tone="bad">{error}</Notice>}
      <label className="field">
        <span>Reporting date</span>
        <input type="date" required value={reportingDate} onChange={(e) => setReportingDate(e.target.value)} />
      </label>
      <div
        className={`drop ${dragging ? "drop-over" : ""} ${file ? "drop-has" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        {file ? (
          <>
            <strong>{file.name}</strong>
            <span className="muted small">{(file.size / 1024).toFixed(0)} KB</span>
          </>
        ) : (
          <span className="muted">Drop the file here, or</span>
        )}
        <button type="button" className="btn" onClick={() => input.current?.click()}>
          {file ? "Choose another file" : "Choose file"}
        </button>
        <input
          ref={input}
          type="file"
          hidden
          accept=".csv,.xlsx,.xlsm,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>
      <details className="tech">
        <summary>More options</summary>
        <label className="field">
          <span>Send to CBK as</span>
          <select value={transport} onChange={(e) => setTransport(e.target.value)}>
            <option value="">Decide automatically (JSON, or CSV for large files)</option>
            <option value="json">JSON payload</option>
            <option value="csv">Attached CSV file</option>
          </select>
        </label>
        <label className="field">
          <span>Replace an earlier CBK request</span>
          <input
            placeholder="CBK request number, e.g. 47202012"
            value={overrideId}
            onChange={(e) => setOverrideId(e.target.value)}
          />
          <small className="muted">Fill this in only to correct data you already filed. CBK overrides that request.</small>
        </label>
      </details>
      <button className="btn btn-primary btn-block" disabled={busy}>
        {busy ? "Checking the file…" : "Upload and check"}
      </button>
    </form>
  );
}
