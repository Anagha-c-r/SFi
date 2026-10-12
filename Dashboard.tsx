import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, EnvTag, Notice, PageHeader, Spinner, StatusBadge, useLoad } from "../components/ui";
import { fmtDate, timeAgo } from "../format";
import type { Dashboard, Submission } from "../types";

export function DashboardPage() {
  const { can } = useAuth();
  const { data, error } = useLoad(() => api.get<Dashboard>("/api/dashboard"), []);
  if (error) return <Notice tone="bad">{error}</Notice>;
  if (!data) return <Spinner />;
  const t = data.totals;

  return (
    <>
      <PageHeader
        title="Overview"
        sub={
          <>
            {data.institution.name} <EnvTag env={data.institution.environment} />
          </>
        }
        actions={
          can("admin", "maker") && (
            <Link className="btn btn-primary" to="/datasets">
              Upload a dataset
            </Link>
          )
        }
      />

      {!data.institution.has_credentials && (
        <Notice tone="warn">
          CBK credentials aren't set up yet, so nothing can be sent.{" "}
          {can("admin") ? <Link to="/settings">Add your client ID and secret</Link> : "Ask your administrator to add them."}
        </Notice>
      )}

      <section className="tally" aria-label="Totals">
        <Tally n={t.pending_approval} label="awaiting approval" to="/approvals" tone={t.pending_approval ? "warn" : undefined} />
        <Tally n={t.failed} label="failed to send" to="/submissions?status=failed" tone={t.failed ? "bad" : undefined} />
        <Tally n={t.invalid} label="uploads with errors" to="/submissions?status=invalid" />
        <Tally n={t.sent} label="sent to CBK" to="/submissions?status=submitted,cbk_accepted,cbk_rejected" />
        <Tally n={t.datasets_reported} of={t.datasets_total} label="datasets filed at least once" to="/datasets" />
      </section>

      <div className="grid-2">
        <section className="panel">
          <h2>Needs attention</h2>
          {data.attention.length ? (
            <SubList items={data.attention} />
          ) : (
            <Empty title="Nothing waiting on you.">Uploads with errors, pending approvals and failed sends show up here.</Empty>
          )}
        </section>
        <section className="panel">
          <h2>Last 30 days</h2>
          <ActivityBars data={data.activity} />
          <h2 className="mt">Recent uploads</h2>
          {data.recent.length ? <SubList items={data.recent} /> : <Empty title="No uploads yet." />}
        </section>
      </div>

      <section className="panel">
        <h2>Filing coverage</h2>
        <p className="muted small">When each dataset was last sent to CBK.</p>
        <div className="coverage">
          {data.coverage.map((d) => (
            <Link key={d.code} to={`/datasets/${d.code}`} className={`cov ${d.last_submitted_at ? "cov-done" : ""}`} title={d.title}>
              <span className="cov-title">{d.title}</span>
              <span className="cov-when">{d.last_submitted_at ? timeAgo(d.last_submitted_at) : "never"}</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

function Tally({ n, of, label, to, tone }: { n: number; of?: number; label: string; to: string; tone?: "warn" | "bad" }) {
  return (
    <Link to={to} className={`tally-item ${tone ? `tally-${tone}` : ""}`}>
      <span className="tally-n">
        {n}
        {of !== undefined && <span className="tally-of">/{of}</span>}
      </span>
      <span className="tally-label">{label}</span>
    </Link>
  );
}

function SubList({ items }: { items: Submission[] }) {
  return (
    <ul className="sublist">
      {items.map((s) => (
        <li key={s.id}>
          <Link to={`/submissions/${s.id}`}>
            <span className="sublist-title">{s.dataset_title}</span>
            <span className="muted small">
              Reporting date {fmtDate(s.reporting_date)}, {s.row_count.toLocaleString()} rows, {timeAgo(s.created_at)}
            </span>
          </Link>
          <StatusBadge status={s.status} />
        </li>
      ))}
    </ul>
  );
}

function ActivityBars({ data }: { data: Dashboard["activity"] }) {
  const max = Math.max(1, ...data.map((d) => d.sent + d.failed + d.other));
  const total = data.reduce((a, d) => a + d.sent + d.failed + d.other, 0);
  const W = 600;
  const H = 120;
  const bw = W / data.length;
  return (
    <figure className="activity">
      <svg viewBox={`0 0 ${W} ${H + 18}`} role="img" aria-label={`${total} uploads in the last 30 days`}>
        {data.map((d, i) => {
          const parts = [
            { v: d.sent, c: "var(--good)" },
            { v: d.other, c: "var(--line-strong)" },
            { v: d.failed, c: "var(--bad)" },
          ];
          let y = H;
          return (
            <g key={d.date}>
              <title>
                {fmtDate(d.date)}: {d.sent} sent, {d.other} in progress, {d.failed} failed or with errors
              </title>
              <rect x={i * bw} y={0} width={bw} height={H} fill="transparent" />
              {parts.map((p, j) => {
                if (!p.v) return null;
                const h = (p.v / max) * (H - 4);
                y -= h;
                return <rect key={j} x={i * bw + 2} y={y} width={bw - 4} height={Math.max(h - 1, 1)} rx={2} fill={p.c} />;
              })}
            </g>
          );
        })}
        <line x1={0} x2={W} y1={H} y2={H} stroke="var(--line-strong)" />
        <text x={0} y={H + 14} className="axis">
          {fmtDate(data[0]?.date)}
        </text>
        <text x={W} y={H + 14} className="axis" textAnchor="end">
          Today
        </text>
      </svg>
      <figcaption className="legend">
        <span className="key key-good" /> Sent <span className="key key-mid" /> In progress <span className="key key-bad" /> Failed or
        errors
      </figcaption>
    </figure>
  );
}
