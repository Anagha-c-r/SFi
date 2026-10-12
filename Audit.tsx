import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Notice, PageHeader, Pager, Spinner, useLoad } from "../components/ui";
import { fmtDateTime } from "../format";
import type { AuditItem, Page } from "../types";

const LABELS: Record<string, string> = {
  "user.login": "Signed in",
  "user.created": "Added a user",
  "user.updated": "Changed a user",
  "user.password_changed": "Changed their password",
  "institution.settings_updated": "Changed CBK settings",
  "institution.connection_tested": "Tested the CBK connection",
  "institution.created": "Institution onboarded",
  "institution.updated": "Institution updated",
  "submission.uploaded": "Uploaded a file",
  "submission.approval_requested": "Sent for approval",
  "submission.approved": "Approved a submission",
  "submission.rejected": "Returned a submission",
  "submission.sent": "Sent to CBK",
  "submission.send_failed": "Sending to CBK failed",
  "submission.retry": "Retried sending",
  "submission.cbk_outcome": "Recorded CBK's result",
  "submission.deleted": "Deleted an upload",
};

function summary(detail: Record<string, unknown>): string {
  return Object.entries(detail)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
    .join("; ");
}

export function Audit() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? 1);
  const { data, error } = useLoad(() => api.get<Page<AuditItem>>(`/api/institution/audit?page=${page}`), [page]);

  return (
    <>
      <PageHeader title="Audit log" sub="Every sign-in, change and submission at your institution. Entries can't be edited or removed." />
      {error && <Notice tone="bad">{error}</Notice>}
      {!data ? (
        <Spinner />
      ) : (
        <section className="panel flush">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>What</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((e) => (
                  <tr key={e.id}>
                    <td className="small nowrap">{fmtDateTime(e.at)}</td>
                    <td>{e.by}</td>
                    <td>
                      {e.entity_type === "submission" && e.entity_id && e.action !== "submission.deleted" ? (
                        <Link to={`/submissions/${e.entity_id}`}>{LABELS[e.action] ?? e.action}</Link>
                      ) : (
                        LABELS[e.action] ?? e.action
                      )}
                    </td>
                    <td className="small muted">{summary(e.detail)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={data.page_size} total={data.total} onPage={(p) => setParams({ page: String(p) })} />
        </section>
      )}
    </>
  );
}
