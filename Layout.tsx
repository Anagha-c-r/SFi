import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { ROLE_LABEL } from "../format";
import { EnvTag } from "./ui";

interface Item {
  to: string;
  label: string;
  show: boolean;
}

export function Layout() {
  const { user, can, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  if (!user) return null;
  const inst = user.institution;

  const sections: { title?: string; items: Item[] }[] = [
    {
      items: [
        { to: "/", label: "Overview", show: !!inst },
        { to: "/datasets", label: "Datasets", show: !!inst },
        { to: "/submissions", label: "Submissions", show: !!inst },
        { to: "/approvals", label: "Approvals", show: !!inst && can("admin", "checker") },
      ],
    },
    {
      title: "Administration",
      items: [
        { to: "/settings", label: "CBK connection", show: can("admin") },
        { to: "/users", label: "Users", show: can("admin") },
        { to: "/audit", label: "Audit log", show: can("admin", "checker") },
        { to: "/admin/institutions", label: "Institutions", show: can("platform_admin") },
      ],
    },
  ];

  return (
    <div className={`shell ${inst?.environment === "prod" ? "shell-prod" : ""}`}>
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            G
          </span>
          <span className="brand-name">
            GDI Portal
            <small>CBK regulatory reporting</small>
          </span>
        </div>
        <nav aria-label="Main">
          {sections.map((s, i) => {
            const items = s.items.filter((it) => it.show);
            if (!items.length) return null;
            return (
              <div className="nav-group" key={i}>
                {s.title && <p className="nav-title">{s.title}</p>}
                {items.map((it) => (
                  <NavLink key={it.to} to={it.to} end={it.to === "/"} className="nav-link" onClick={() => setOpen(false)}>
                    {it.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <NavLink to="/account" className="who" onClick={() => setOpen(false)}>
            <span className="who-name">{user.full_name}</span>
            <span className="who-role">{ROLE_LABEL[user.role]}</span>
          </NavLink>
          <button className="btn btn-on-dark" onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <button className="btn btn-quiet menu-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
            Menu
          </button>
          {inst ? (
            <div className="topbar-inst">
              <strong>{inst.name}</strong>
              <span className="muted">CBK code {inst.institution_code}</span>
              <EnvTag env={inst.environment} />
            </div>
          ) : (
            <div className="topbar-inst">
              <strong>Finoworks platform administration</strong>
            </div>
          )}
        </div>
        {inst?.environment === "prod" && (
          <div className="prod-strip">You are working against CBK production. Approved submissions are filed for real.</div>
        )}
        <main className="content" key={loc.pathname}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
