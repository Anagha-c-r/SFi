export type Role = "platform_admin" | "admin" | "maker" | "checker" | "viewer";

export type Status =
  | "invalid"
  | "validated"
  | "pending_approval"
  | "rejected"
  | "queued"
  | "sending"
  | "submitted"
  | "failed"
  | "cbk_accepted"
  | "cbk_rejected";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  institution: { id: string; name: string; institution_code: string; environment: "uat" | "prod" } | null;
  last_login_at: string | null;
  created_at: string;
}

export interface DatasetSummary {
  number: number;
  code: string;
  title: string;
  group: string;
  frequency: string;
  field_count: number;
  notes: string;
}

export interface FieldDef {
  key: string;
  name: string;
  payload_key: string;
  type: "string" | "number" | "date";
  required: boolean;
  description: string;
  example: string;
}

export interface DatasetDetail extends DatasetSummary {
  endpoint: string;
  array_key: string;
  source_pages: [number, number];
  fields: FieldDef[];
}

export interface Issue {
  row: number | null;
  field: string | null;
  value: string | null;
  message: string;
  level: "error" | "warning";
}

export interface Submission {
  id: string;
  dataset_code: string;
  dataset_title: string;
  reporting_date: string;
  status: Status;
  original_filename: string | null;
  row_count: number;
  error_count: number;
  warning_count: number;
  override_request_id: string | null;
  transport: "json" | "csv";
  environment: "uat" | "prod";
  cbk_request_no: string | null;
  cbk_status_text: string | null;
  cbk_http_status: number | null;
  last_error: string | null;
  attempts: number;
  review_note: string | null;
  created_by_id: string;
  created_by_name: string;
  approved_by_name: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
}

export interface SubmissionDetail extends Submission {
  issues: Issue[];
  column_map: Record<string, string>;
  cbk_response: Record<string, unknown> | null;
  preview_rows: Record<string, string>[];
  events: { action: string; at: string; by: string; detail: Record<string, unknown> }[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Institution {
  id: string;
  name: string;
  institution_code: string;
  category: string;
  environment: "uat" | "prod";
  cbk_client_id: string | null;
  has_credentials: boolean;
  cbk_scope: string | null;
  notification_email: string | null;
  four_eyes: boolean;
  date_format: string;
  is_active: boolean;
  created_at: string;
}

export interface Dashboard {
  institution: { name: string; code: string; environment: "uat" | "prod"; has_credentials: boolean };
  totals: {
    sent: number;
    pending_approval: number;
    failed: number;
    invalid: number;
    in_flight: number;
    datasets_reported: number;
    datasets_total: number;
  };
  by_status: Record<string, number>;
  activity: { date: string; sent: number; failed: number; other: number }[];
  coverage: (DatasetSummary & { last_submitted_at: string | null })[];
  attention: Submission[];
  recent: Submission[];
}

export interface AuditItem {
  id: number;
  at: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  by: string;
  detail: Record<string, unknown>;
}
