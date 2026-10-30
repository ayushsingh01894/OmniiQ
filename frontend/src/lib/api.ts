import { getToken } from "./session";

// ---------- types (mirror the backend schemas) ----------
export type Role = "viewer" | "member" | "admin" | "owner";

export type User = { id: string; email: string; display_name: string; created_at: string };
export type Token = { access_token: string; token_type: "bearer"; expires_in: number };
export type Organization = {
  id: string;
  name: string;
  slug: string;
  role: Role;
  created_at: string;
};
export type Project = {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};
export type ProjectPage = { items: Project[]; total: number; limit: number; offset: number };
export type DType = "integer" | "float" | "boolean" | "datetime" | "string";
export type ColumnSchema = { name: string; dtype: DType; nullable: boolean };
export type DatasetVersion = {
  id: string;
  version: number;
  parent_version: number | null;
  row_count: number;
  column_count: number;
  size_bytes: number;
  checksum_sha256: string;
  columns: ColumnSchema[];
  operations: Record<string, unknown>[] | null;
  created_at: string;
};
export type DatasetStatus = "processing" | "ready" | "failed";
export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  original_filename: string;
  format: "csv" | "xlsx";
  status: DatasetStatus;
  original_size_bytes: number;
  created_at: string;
  latest_version: DatasetVersion | null;
};
export type DatasetDetail = Dataset & { versions: DatasetVersion[] };
export type DatasetPage = { items: Dataset[]; total: number; limit: number; offset: number };
export type JobStatusValue = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type Job = {
  id: string;
  dataset_id: string;
  job_type: "ingest" | "profile" | "clean";
  status: JobStatusValue;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export type Preview = {
  version: number;
  columns: ColumnSchema[];
  rows: Record<string, unknown>[];
  total_rows: number;
  limit: number;
  offset: number;
};
export type ProfileColumn = {
  name: string;
  dtype: DType;
  missing: number;
  missing_pct: number;
  unique: number;
  stats: Record<string, number | string | null> | null;
  top_values: { value: string; count: number }[] | null;
};
export type Profile = {
  version: number;
  row_count: number;
  column_count: number;
  duplicate_rows: number;
  missing_cells: number;
  columns: ProfileColumn[];
  issues: { severity: string; column: string | null; code: string; message: string }[];
};
export type ReadyResponse = { status: "ready" | "not_ready"; database: "up" | "down" };

// ---------- errors ----------
export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: FieldError[];

  constructor(status: number, code: string, message: string, details: FieldError[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// ---------- core request ----------
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

let unauthorizedHandler: (() => void) | null = null;
/** Called when an authenticated request is rejected with 401 (expired/invalid token). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

type RequestOptions = { method?: string; body?: unknown; auth?: boolean };

async function request<T>(path: string, { method = "GET", body, auth = true }: RequestOptions = {}) {
  const headers: Record<string, string> = { Accept: "application/json" };
  const isForm = body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const token = auth ? getToken() : null;
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });

  if (res.status === 204) return undefined as T;

  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    // non-JSON body: fall through to the generic error below
  }

  if (!res.ok) {
    const err = (payload as { error?: { code?: string; message?: string; details?: FieldError[] } })
      ?.error;
    if (res.status === 401 && auth && token) unauthorizedHandler?.();
    throw new ApiError(
      res.status,
      err?.code ?? "unknown_error",
      err?.message ?? `Request failed (${res.status}).`,
      err?.details ?? [],
    );
  }
  return payload as T;
}

// ---------- endpoints ----------
export const register = (body: { email: string; password: string; display_name: string }) =>
  request<User>("/auth/register", { method: "POST", body, auth: false });

export const login = (body: { email: string; password: string }) =>
  request<Token>("/auth/login", { method: "POST", body, auth: false });

export const getMe = () => request<User>("/auth/me");
export const listOrganizations = () => request<Organization[]>("/organizations");
export const listProjects = () => request<ProjectPage>("/projects");
export const createProject = (body: {
  organization_id: string;
  name: string;
  description?: string;
}) => request<Project>("/projects", { method: "POST", body });
export const getProject = (id: string) => request<Project>(`/projects/${id}`);

export const listDatasets = (projectId: string) =>
  request<DatasetPage>(`/projects/${projectId}/datasets`);
export const getDataset = (id: string) => request<DatasetDetail>(`/datasets/${id}`);
export const deleteDataset = (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" });
export const uploadDataset = (projectId: string, file: File, name: string) => {
  const form = new FormData();
  form.append("file", file);
  if (name.trim()) form.append("name", name.trim());
  return request<{ dataset: Dataset; job: Job }>(`/projects/${projectId}/datasets`, {
    method: "POST",
    body: form,
  });
};
export const getPreview = (id: string, version: number, offset: number, limit = 25) =>
  request<Preview>(`/datasets/${id}/preview?version=${version}&offset=${offset}&limit=${limit}`);
export const getProfile = (id: string, version: number) =>
  request<Profile>(`/datasets/${id}/profile?version=${version}`);
export const requestCleaning = (id: string, body: { base_version: number; operations: unknown[] }) =>
  request<Job>(`/datasets/${id}/cleaning-jobs`, { method: "POST", body });
export const listJobs = (datasetId: string) => request<Job[]>(`/datasets/${datasetId}/jobs`);
export const getJob = (id: string) => request<Job>(`/jobs/${id}`);

/** Downloads need the Authorization header, so a plain <a href> cannot be used. */
export async function downloadExport(id: string, version: number, format: "csv" | "json") {
  const token = getToken();
  const res = await fetch(`${API_BASE}/api/v1/datasets/${id}/export?version=${version}&format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "export_failed", "The export could not be created.");
  const blob = await res.blob();
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = match?.[1] ?? `dataset_v${version}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export const deleteProject = (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" });

/**
 * Readiness. The backend answers 503 with a valid body when the database is down;
 * that is data the UI should show, not an exception. Any other failure throws.
 */
export async function getReadiness(): Promise<ReadyResponse> {
  const res = await fetch(`${API_BASE}/api/v1/health/ready`, {
    headers: { Accept: "application/json" },
  });
  if (res.ok || res.status === 503) {
    return (await res.json()) as ReadyResponse;
  }
  throw new ApiError(res.status, "unexpected_response", `Unexpected response (${res.status}).`);
}
