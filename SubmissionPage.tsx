import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { EnvTag, Notice, PageHeader, Spinner, StatusBadge, useLoad } from "../components/ui";
import { fmtDate, fmtDateTime } from "../format";
import type { Status, SubmissionDetail } from "../types";

type StepState = "done" | "current" | "todo" | "bad";

function steps(s: Status): { label: string; state: StepState }[] {
  const order: Record<Status, number> = {
    invalid: 1, validated: 1, rejected: 2, pending_approval: 2, queued: 3, sending: 3, failed: 3,
    submitted: 4, cbk_accepted: 5, cbk_rejected: 5,
  };
  const at = order[s];
  const bad = s === "invalid" ? 1 : s === "rejected" ? 2 : s === "failed" ? 3 : s === "cbk_rejected" ? 4 : -1;
  const labels = ["Uploaded", "File check", "Approval", "Sent to CBK", "CBK result"];
  return labels.map((label, i) => ({
    label,
    state: i === bad ? "bad" : i < at || (i === at && at === 5) ? "done" : i === at ? "current" : "todo",
  }));
}

const STEP_NOTE: Record<Status, string> = {
  invalid: "The file has errors. Fix them in your source file and upload it again.",
  validated: "The file passed every check. Send it for approval when you're ready.",
  pending_approval: "Waiting for an approver. Approving sends it to CBK.",
  rejected: "An approver returned this upload.",
  queued: "Approved. Sending to CBK…",
  sending: "Sending to CBK…",
  failed: "CBK didn't accept the request. See the reason below, then retry.",
  submitted: "CBK accepted the request. Its validation result arrives by email; record it here when it does.",
  cbk_accepted: "CBK accepted the data.",
  cbk_rejected: "CBK rejected the data after validation. Upload a corrected file that replaces this request.",
};

export function SubmissionPage() {
  const { id = "" } = useParams();
  const { user, can } = useAuth();
  const nav = useNavigate();
  const { data: s, error, reload } = useLoad(() => api.get<SubmissionDetail>(`/api/submissions/${id}`), [id]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [tab, setTab] = useState<"issues" | "data" | "history">("issues");

  const inFlight = s?.status === "queued" || s?.status === "sending";
  useEffect(() => {
    if (!inFlight) return;
    const t = setInterval(reload, 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inFlight]);

  useEffect(() => {
    if (s) setTab(s.issues.length ? "issues" : "data");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s?.id]);

  if (error) return <Notice tone="bad">{error}</Notice>;
  if (!s) return <Spinner />;

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setActionError(null);
    try {
      await api.post(`/api/submissions/${id}/${path}`, body);
      setRejecting(false);
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this upload? This can't be undone.")) return;
    try {
      await api.del(`/api/submissions/${id}`);
      nav("/submissions");
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  const isMaker = can("admin", "maker");
  const isChecker = can("admin", "checker");
  const ownUpload = s.created_by_id === user?.id;
  const errors = s.issues.filter((i) => i.level === "error");
  const warnings = s.issues.filter((i) => i.level === "warning");
  const columns = s.preview_rows[0] ? Object.keys(s.preview_rows[0]) : [];

  return (
    <>
      <p className="crumb">
        <Link to="/submissions">Submissions</Link> / <Link to={`/datasets/${s.dataset_code}`}>{s.dataset_title}</Link>
      </p>
      <PageHeader
        title={`${s.dataset_title}, ${fmtDate(s.reporting_date)}`}
        sub={
          <>
            <StatusBadge status={s.status} /> {s.row_count.toLocaleString()} rows from {s.original_filename}{" "}
            <EnvTag env={s.environment} />
          </>
        }
      />

      <ol className="pipeline" aria-label="Progress">
        {steps(s.status).map((st, i) => (
          <li key={st.label} className={`step step-${st.state}`} aria-current={st.state === "current" ? "step" : undefined}>
            <span className="step-n">{i + 1}</span>
            <span className="step-label">{st.label}</span>
          </li>
        ))}
      </ol>

      <section className="panel next">
        <p className="next-note">{STEP_NOTE[s.status]}</p>
        {s.review_note && (
          <p className="quote">
            <strong>Note:</strong> {s.review_note}
          </p>
        )}
        {s.last_error && s.status === "failed" && <Notice tone="bad">{s.last_error}</Notice>}
        {actionError && <Notice tone="bad">{actionError}</Notice>}

        <div className="actions">
          {(s.status === "validated" || s.status === "rejected") && isMaker && s.error_count === 0 && (
            <button className="btn btn-primary" disabled={busy} onClick={() => act("request-approval")}>
              Send for approval
            </button>
          )}
          {s.status === "pending_approval" && isChecker && !rejecting && (
            <>
              <button className="btn btn-primary" disabled={busy} onClick={() => act("approve")}>
                Approve and send to CBK
              </button>
              <button className="btn" disabled={busy} onClick={() => setRejecting(true)}>
                Return to preparer
              </button>
              {ownUpload && <span className="muted small">You uploaded this. If four-eyes approval is on, someone else must approve it.</span>}
            </>
          )}
          {s.status === "failed" && isChecker && (
            <button className="btn btn-primary" disabled={busy} onClick={() => act("retry")}>
              Retry sending
            </button>
          )}
          {s.status === "submitted" && (isMaker || isChecker) && (
            <>
              <button className="btn" disabled={busy} onClick={() => act("outcome", { accepted: true })}>
                CBK accepted it
              </button>
              <button className="btn" disabled={busy} onClick={() => setRejecting(true)}>
                CBK rejected it
              </button>
            </>
          )}
          {(s.status === "invalid" || s.status === "cbk_rejected") && isMaker && (
            <Link className="btn btn-primary" to={`/datasets/${s.dataset_code}`}>
              Upload a corrected file
            </Link>
          )}
          {["invalid", "validated", "rejected"].includes(s.status) && isMaker && (
            <button className="btn btn-danger-quiet" onClick={remove}>
              Delete upload
            </button>
          )}
        </div>

        {rejecting && (
          <form
            className="reject"
            onSubmit={(e) => {
              e.preventDefault();
              if (s.status === "submitted") void act("outcome", { accepted: false, note });
              else void act("reject", { note });
            }}
          >
            <label className="field">
              <span>{s.status === "submitted" ? "What did CBK say?" : "What needs to change?"}</span>
              <textarea required rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
            <div className="actions">
              <button className="btn btn-primary" disabled={busy}>
                {s.status === "submitted" ? "Record CBK rejection" : "Return to preparer"}
              </button>
              <button type="button" className="btn btn-quiet" onClick={() => setRejecting(false)}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>

      <div className="grid-2 grid-wide-left">
        <section className="panel">
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === "issues"} className={`tab ${tab === "issues" ? "tab-on" : ""}`} onClick={() => setTab("issues")}>
              Check results ({errors.length} errors, {warnings.length} warnings)
            </button>
            <button role="tab" aria-selected={tab === "data"} className={`tab ${tab === "data" ? "tab-on" : ""}`} onClick={() => setTab("data")}>
              Data preview
            </button>
            <button role="tab" aria-selected={tab === "history"} className={`tab ${tab === "history" ? "tab-on" : ""}`} onClick={() => setTab("history")}>
              History
            </button>
          </div>

          {tab === "issues" &&
            (s.issues.length === 0 ? (
              <p className="good-text">Every row passed the checks.</p>
            ) : (
              <>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th className="num">Row</th>
                        <th>Column</th>
                        <th>Value</th>
                        <th>Problem</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.issues.slice(0, 200).map((i, n) => (
                        <tr key={n} className={i.level === "warning" ? "row-warn" : "row-bad"}>
                          <td className="num">{i.row ?? "File"}</td>
                          <td>{i.field ?? "—"}</td>
                          <td className="mono small">{i.value || "—"}</td>
                          <td>{i.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {s.issues.length > 200 && <p className="muted small">Showing the first 200. Download the full list below.</p>}
                <button className="btn btn-quiet" onClick={() => download(`/api/submissions/${id}/issues.csv`, "issues.csv")}>
                  Download all check results
                </button>
              </>
            ))}

          {tab === "data" && (
            <>
              <p className="muted small">
                The first {Math.min(s.preview_rows.length, 50)} of {s.row_count.toLocaleString()} rows, as they will be sent to CBK.
              </p>
              <div className="table-wrap preview">
                <table className="table table-dense">
                  <thead>
                    <tr>
                      {columns.map((c) => (
                        <th key={c}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.preview_rows.map((r, n) => (
                      <tr key={n}>
                        {columns.map((c) => (
                          <td key={c}>{r[c]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === "history" && (
            <ol className="timeline">
              {s.events.map((e, n) => (
                <li key={n}>
                  <span className="tl-when small muted">{fmtDateTime(e.at)}</span>
                  <span>
                    {describe(e.action)} <span className="muted">by {e.by}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="panel">
          <h2>Details</h2>
          <dl className="kv">
            <dt>CBK request number</dt>
            <dd className="mono">{s.cbk_request_no ?? "Not sent yet"}</dd>
            {s.cbk_status_text && (
              <>
                <dt>CBK response</dt>
                <dd>{s.cbk_status_text}</dd>
              </>
            )}
            <dt>Sent as</dt>
            <dd>{s.transport === "csv" ? "Attached CSV file" : "JSON payload"}</dd>
            {s.override_request_id && (
              <>
                <dt>Replaces request</dt>
                <dd className="mono">{s.override_request_id}</dd>
              </>
            )}
            <dt>Uploaded by</dt>
            <dd>
              {s.created_by_name}, {fmtDateTime(s.created_at)}
            </dd>
            <dt>Approved by</dt>
            <dd>{s.approved_by_name ?? "—"}</dd>
            <dt>Sent</dt>
            <dd>{fmtDateTime(s.submitted_at)}</dd>
            {s.attempts > 1 && (
              <>
                <dt>Send attempts</dt>
                <dd>{s.attempts}</dd>
              </>
            )}
          </dl>
          <div className="stack-sm">
            <button className="btn btn-quiet" onClick={() => download(`/api/submissions/${id}/payload.json`, "payload.json")}>
              Download CBK payload (JSON)
            </button>
            <button className="btn btn-quiet" onClick={() => download(`/api/submissions/${id}/data.csv`, "data.csv")}>
              Download cleaned data (CSV)
            </button>
          </div>
          {s.cbk_response && (
            <details className="tech">
              <summary>Raw CBK response</summary>
              <pre>{JSON.stringify(s.cbk_response, null, 2)}</pre>
            </details>
          )}
        </section>
      </div>
    </>
  );
}

const ACTIONS: Record<string, string> = {
  "submission.uploaded": "Uploaded and checked",
  "submission.approval_requested": "Sent for approval",
  "submission.approved": "Approved",
  "submission.rejected": "Returned to preparer",
  "submission.sent": "Sent to CBK",
  "submission.send_failed": "Sending failed",
  "submission.retry": "Retry requested",
  "submission.cbk_outcome": "CBK result recorded",
};
const describe = (a: string) => ACTIONS[a] ?? a;
