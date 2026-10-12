import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Notice, PageHeader, Spinner, useLoad } from "../components/ui";
import type { DatasetSummary } from "../types";

export function Datasets() {
  const { data, error } = useLoad(() => api.get<DatasetSummary[]>("/api/datasets"), []);
  const [q, setQ] = useState("");

  const groups = useMemo(() => {
    const term = q.trim().toLowerCase();
    const out = new Map<string, DatasetSummary[]>();
    for (const d of data ?? []) {
      if (term && !d.title.toLowerCase().includes(term) && !d.group.toLowerCase().includes(term)) continue;
      out.set(d.group, [...(out.get(d.group) ?? []), d]);
    }
    return [...out.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [data, q]);

  if (error) return <Notice tone="bad">{error}</Notice>;
  if (!data) return <Spinner />;

  return (
    <>
      <PageHeader
        title="Datasets"
        sub={`The ${data.length} returns defined in CBK's GDI guide. Pick one to see its fields, download a template or upload data.`}
      />
      <div className="toolbar">
        <input
          className="search"
          type="search"
          placeholder="Find a dataset, e.g. loans or forex"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Find a dataset"
        />
      </div>
      {groups.length === 0 && <p className="muted">No dataset matches “{q}”.</p>}
      <div className="ds-groups">
        {groups.map(([group, items]) => (
          <section key={group} className="ds-group">
            <h2>{group}</h2>
            <ul>
              {items.map((d) => (
                <li key={d.code}>
                  <Link to={`/datasets/${d.code}`} className="ds-link">
                    <span>{d.title}</span>
                    <span className="muted small">
                      {d.field_count} fields{d.frequency === "weekly" ? ", weekly" : ""}
                      {d.notes ? ", endpoint to confirm" : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
