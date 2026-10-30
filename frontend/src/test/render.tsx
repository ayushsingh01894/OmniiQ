import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AppRoutes } from "../app/routes";
import { AuthProvider } from "../features/auth/AuthProvider";
import type { DatasetDetail, DatasetVersion, Job, Organization, Project, Role, User } from "../lib/api";
import { storeToken } from "../lib/session";

export const ana: User = {
  id: "u1",
  email: "ana@example.com",
  display_name: "Ana",
  created_at: "2026-01-01T00:00:00Z",
};

export function org(id: string, name: string, role: Role): Organization {
  return { id, name, slug: id, role, created_at: "2026-01-01T00:00:00Z" };
}

export function project(id: string, name: string, organization_id: string): Project {
  return {
    id,
    organization_id,
    name,
    description: null,
    created_by: "u1",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  };
}

/** [status, body, headers?] | "network-error" | "pending" (never resolves) | (url, body) => [status, body] */
export type Route =
  | [number, unknown]
  | [number, unknown, Record<string, string>]
  | "network-error"
  | "pending"
  | ((url: string, body: unknown) => [number, unknown]);
export type Routes = Record<string, Route>;
export type Call = { key: string; body: unknown; url: string; headers: Record<string, string> | undefined };

/**
 * Stubs fetch by "METHOD /path". The routes object is read at call time, so a test can change a
 * route mid-test. Unhandled requests fail loudly instead of hanging.
 */
export function mockApi(routes: Routes) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string, init?: RequestInit) => {
      const url = String(input);
      const path = url.split("?")[0];
      const key = `${(init?.method ?? "GET").toUpperCase()} ${path}`;
      const body =
        init?.body instanceof FormData
          ? Object.fromEntries(init.body.entries())
          : init?.body
            ? JSON.parse(String(init.body))
            : undefined;
      calls.push({ key, body, url, headers: init?.headers as Record<string, string> | undefined });
      const route = routes[key];
      if (route === undefined) return Promise.reject(new Error(`Unhandled request: ${key}`));
      if (route === "network-error") return Promise.reject(new TypeError("Failed to fetch"));
      if (route === "pending") return new Promise(() => {});
      const [status, payload, headers] =
        typeof route === "function" ? [...route(url, body), undefined] : route;
      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        headers: new Headers(headers),
        json: () => Promise.resolve(payload),
        blob: () => Promise.resolve(new Blob([typeof payload === "string" ? payload : JSON.stringify(payload)])),
      });
    }),
  );
  return { routes, calls };
}

export const READY: Route = [200, { status: "ready", database: "up" }];

export function renderApp(initialPath = "/", { signedIn = true } = {}) {
  if (signedIn) storeToken("test-token");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}


export function version(n: number, extra: Partial<DatasetVersion> = {}): DatasetVersion {
  return {
    id: `v${n}`,
    version: n,
    parent_version: n > 1 ? n - 1 : null,
    row_count: 3,
    column_count: 2,
    size_bytes: 100,
    checksum_sha256: `sha${n}`,
    columns: [
      { name: "id", dtype: "integer", nullable: false },
      { name: "name", dtype: "string", nullable: true },
    ],
    operations: null,
    created_at: "2026-01-03T00:00:00Z",
    ...extra,
  };
}

export function dataset(extra: Partial<DatasetDetail> = {}): DatasetDetail {
  const versions = extra.versions ?? [version(1)];
  return {
    id: "d1",
    project_id: "p1",
    name: "Sales",
    original_filename: "sales.csv",
    format: "csv",
    status: "ready",
    original_size_bytes: 2048,
    created_at: "2026-01-03T00:00:00Z",
    latest_version: versions[versions.length - 1] ?? null,
    versions,
    ...extra,
  };
}

export function job(id: string, extra: Partial<Job> = {}): Job {
  return {
    id,
    dataset_id: "d1",
    job_type: "ingest",
    status: "queued",
    progress: 0,
    error_code: null,
    error_message: null,
    result: null,
    created_at: "2026-01-03T00:00:00Z",
    started_at: null,
    finished_at: null,
    ...extra,
  };
}
