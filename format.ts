import type { Role, Status } from "./types";

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function parse(value: string): Date {
  // API timestamps without a zone are UTC
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) || value.length <= 10 ? value : value + "Z");
}

export const fmtDate = (v: string | null | undefined) => (v ? dateFmt.format(parse(v)) : "—");
export const fmtDateTime = (v: string | null | undefined) => (v ? dateTimeFmt.format(parse(v)) : "—");
export const fmtNumber = (n: number) => n.toLocaleString("en-GB");

export function timeAgo(v: string | null | undefined): string {
  if (!v) return "never";
  const secs = (Date.now() - parse(v).getTime()) / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  const days = Math.floor(secs / 86400);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export const STATUS_LABEL: Record<Status, string> = {
  invalid: "Has errors",
  validated: "Ready for approval",
  pending_approval: "Awaiting approval",
  rejected: "Returned",
  queued: "Queued",
  sending: "Sending",
  submitted: "Sent to CBK",
  failed: "Send failed",
  cbk_accepted: "Accepted by CBK",
  cbk_rejected: "Rejected by CBK",
};

export type Tone = "neutral" | "good" | "warn" | "bad" | "info";

export const STATUS_TONE: Record<Status, Tone> = {
  invalid: "bad",
  validated: "neutral",
  pending_approval: "warn",
  rejected: "warn",
  queued: "info",
  sending: "info",
  submitted: "info",
  failed: "bad",
  cbk_accepted: "good",
  cbk_rejected: "bad",
};

export const ROLE_LABEL: Record<Role, string> = {
  platform_admin: "Platform admin",
  admin: "Administrator",
  maker: "Preparer",
  checker: "Approver",
  viewer: "Viewer",
};

export const ROLE_HELP: Record<Exclude<Role, "platform_admin">, string> = {
  admin: "Manages users and CBK credentials, and can prepare and approve.",
  maker: "Uploads data and sends it for approval.",
  checker: "Approves submissions so they go to CBK.",
  viewer: "Can look at everything, change nothing.",
};
