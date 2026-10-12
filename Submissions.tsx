import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Empty, Notice, PageHeader, Pager, Spinner, StatusBadge, useLoad } from "../components/ui";
import { fmtDate, fmtDateTime, STATUS_LABEL } from "../format";
import type { DatasetSummary, Page, Status, Submission } from "../types";

const FILTERS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Awaiting approval", value: "pending_approval" },
  { label: "Has errors", value: "invalid" },
  { label: "Ready for approval", value: "validated" },
  { label: "Send failed", value: "failed" },
  { label: "Sent to CBK", value: "submitted,cbk_accepted,cbk_rejected" },
];

export function Submissions({ approvals = false }: { approvals?: boolean }) {
  const [params, setParams] = useSearchParams();
  const status = approvals ? "pending_approval" : params.get("status") ?? "";
  const dataset = params.get("dataset") ?? "";
  const [q, setQ] = useState(params.get("q") ?? "");
  const page = Number(params.get("page") ?? 1);

  const qs = new URLSearchParams({ page: String(page), page_size: "25" });
  if (status) qs.set("status", status);
  if (dataset) qs.set("dataset", dataset);
  if (params.get("q")) qs.set("q", params.get("q")!);
  const { data, error } = useLoad(() => api.get<Page<Submission>>(`/api/submissions?${qs}`), [qs.toString()]);
  const datasets = useLoad(() => api.get<DatasetSummary[]>("/api/datasets"), []);

  function set(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  }

  return (
    <>
      <PageHeader
        title={approvals ? "Approvals" : "Submissions"}
        sub={
          approvals
            ? "Uploads waiting for an approver. Approving sends the data to CBK straight away."
            : "Every upload, from first check to CBK's response."
        }
      />
      {!approvals && (
        <div className="toolbar">
          <div className="seg" role="group" aria-label="Filter by status">
            {FILTERS.map((f) => (
              <button key={f.label} className={`seg-btn ${status === f.value ? "seg-on" : ""}`} onClick={() => set("status", f.value)}>
                {f.label}
              </button>
            ))}
          </div>
          <select value={dataset} onChange={(e) => set("dataset", e.target.value)} aria-label="Filter by dataset">
            <option value="">All datasets</option>
            {datasets.data?.map((d) => (
              <option key={d.code} value={d.code}>
                {d.title}
              </option>
            ))}
          </select>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              set("q", q.trim());
            }}
          >
            <input className="search" type="search" placeholder="Request number or file name" value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
        </div>
      )}
      {error && <Notice tone="bad">{error}</Notice>}
      {!data ? (
        <Spinner />
      ) : data.items.length === 0 ? (
        approvals ? (
          <Empty title="No submissions are waiting for approval." />
        ) : (
          <Empty title={status ? `No submissions with status “${STATUS_LABEL[status.split(",")[0] as Status] ?? status}”.` : "No uploads yet."}>
            <Link to="/datasets">Choose a dataset to upload</Link>
          </Empty>
        )
      ) : (
        <section className="panel flush">
          <div className="table-wrap">
            <table className="table table-click">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Reporting date</th>
                  <th className="num">Rows</th>
                  <th>Status</th>
                  <th>CBK request</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <Link to={`/submissions/${s.id}`} className="row-link">
                        {s.dataset_title}
                      </Link>
                      <div className="muted small">{s.original_filename}</div>
                    </td>
                    <td>{fmtDate(s.reporting_date)}</td>
                    <td className="num">{s.row_count.toLocaleString()}</td>
                    <td>
                      <StatusBadge status={s.status} />
                      {s.error_count > 0 && <div className="small bad-text">{s.error_count.toLocaleString()} errors</div>}
                    </td>
                    <td className="mono small">{s.cbk_request_no ?? "—"}</td>
                    <td className="small">
                      {fmtDateTime(s.created_at)}
                      <div className="muted">{s.created_by_name}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={data.page_size} total={data.total} onPage={(p) => set("page", String(p))} />
        </section>
      )}
    </>
  );
}
