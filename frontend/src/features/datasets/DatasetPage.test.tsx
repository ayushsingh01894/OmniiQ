import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ana, dataset, job, mockApi, org, project, renderApp, version, type Routes } from "../../test/render";

afterEach(() => vi.unstubAllGlobals());

const ME = "GET /api/v1/auth/me";
const ORGS = "GET /api/v1/organizations";
const PROJ = "GET /api/v1/projects/p1";
const DS = "GET /api/v1/datasets/d1";
const PREVIEW = "GET /api/v1/datasets/d1/preview";
const PROFILE = "GET /api/v1/datasets/d1/profile";
const CLEAN = "POST /api/v1/datasets/d1/cleaning-jobs";
const JOBS = "GET /api/v1/datasets/d1/jobs";

const rows = (n: number, start = 0) => Array.from({ length: n }, (_, i) => ({ id: start + i + 1, name: i === 1 ? null : `row${start + i + 1}` }));
const previewRoute = (total: number) => (url: string): [number, unknown] => {
  const offset = Number(new URL(url, "http://x").searchParams.get("offset") ?? 0);
  return [200, { version: 1, columns: version(1).columns, rows: rows(Math.min(25, total - offset), offset), total_rows: total, limit: 25, offset }];
};

function setup(role = "owner", extra: Routes = {}) {
  return mockApi({
    [ME]: [200, ana],
    [ORGS]: [200, [org("o1", "Acme", role as "owner")]],
    [PROJ]: [200, project("p1", "Churn study", "o1")],
    [DS]: [200, dataset()],
    [PREVIEW]: previewRoute(3),
    ...extra,
  });
}

describe("DatasetPage states", () => {
  it("shows progress while the file is still being read", async () => {
    setup("owner", {
      [DS]: [200, dataset({ status: "processing", versions: [], latest_version: null })],
      [JOBS]: [200, [job("j1", { status: "running", progress: 70 })]],
      "GET /api/v1/jobs/j1": [200, job("j1", { status: "running", progress: 70 })],
    });
    renderApp("/datasets/d1");
    expect(await screen.findByText("We're reading your file")).toBeInTheDocument();
    expect(await screen.findByRole("progressbar")).toHaveAttribute("aria-valuenow", "70");
  });

  it("explains a failed file and says the original was kept", async () => {
    setup("owner", {
      [DS]: [200, dataset({ status: "failed", versions: [], latest_version: null })],
      [JOBS]: [200, [job("j1", { status: "failed", error_message: "Column names must be unique." })]],
    });
    renderApp("/datasets/d1");
    expect(await screen.findByText("Column names must be unique.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/original upload was kept/i);
  });

  it("shows not-found for a dataset you can't open", async () => {
    setup("owner", { [DS]: [404, { error: { code: "dataset_not_found", message: "x" } }] });
    renderApp("/datasets/d1");
    expect(await screen.findByRole("heading", { name: "Dataset not found" })).toBeInTheDocument();
  });
});

describe("Preview, Profile, History", () => {
  it("shows rows with missing values as a dash and pages through them", async () => {
    setup("owner", { [PREVIEW]: previewRoute(30) });
    renderApp("/datasets/d1");
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: /name string/ })).toBeInTheDocument();
    expect(within(table).getAllByText("—")).toHaveLength(1);
    expect(screen.getByText("Rows 1–25 of 30")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Rows 26–30 of 30")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows the quality profile", async () => {
    setup("owner", {
      [PROFILE]: [200, {
        version: 1, row_count: 4, column_count: 2, duplicate_rows: 1, missing_cells: 2,
        columns: [
          { name: "amount", dtype: "float", missing: 2, missing_pct: 50, unique: 2, stats: { min: 7, max: 10.5, mean: 8.75 }, top_values: null },
          { name: "name", dtype: "string", missing: 0, missing_pct: 0, unique: 2, stats: null, top_values: [{ value: "Ann", count: 3 }] },
        ],
        issues: [{ severity: "warning", column: "amount", code: "high_missing", message: "50% of values are missing." }],
      }],
    });
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("tab", { name: "Profile" }));
    expect(await screen.findByText("Duplicate rows")).toBeInTheDocument();
    expect(screen.getByText("50% of values are missing.")).toBeInTheDocument();
    expect(screen.getByText("min 7 · mean 8.75 · max 10.5")).toBeInTheDocument();
    expect(screen.getByText("Ann (3)")).toBeInTheDocument();
  });

  it("lists versions with the steps that produced them", async () => {
    setup("owner", {
      [DS]: [200, dataset({ versions: [version(1), version(2, { operations: [{ op: "drop_duplicates", keep: "first" }] })] })],
    });
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("tab", { name: "History" }));
    expect(screen.getByText(/from version 1/)).toBeInTheDocument();
    expect(screen.getByText("Remove duplicate rows, keep first")).toBeInTheDocument();
    expect(screen.getByText(/original upload/)).toBeInTheDocument();
  });
});

describe("Cleaning", () => {
  async function openClean() {
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("tab", { name: "Clean" }));
  }

  it("rejects incomplete steps and lets you remove steps", async () => {
    setup();
    await openClean();
    await userEvent.selectOptions(screen.getByLabelText("Step"), "rename_column");
    await userEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(await screen.findByText("Enter the new column name.")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Step"), "drop_duplicates");
    await userEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(screen.getByText("Remove duplicate rows, keep first")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove step 1" }));
    expect(screen.getByText("No steps yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run on version 1/ })).toBeDisabled();
  });

  it("runs steps as a job and switches to the new version when it succeeds", async () => {
    const { routes, calls } = setup("owner", {
      [CLEAN]: [202, job("c1", { job_type: "clean" })],
      "GET /api/v1/jobs/c1": [200, job("c1", { job_type: "clean", status: "running", progress: 30 })],
    });
    await openClean();
    await userEvent.click(screen.getByRole("button", { name: "Add step" })); // duplicates, whole rows
    await userEvent.selectOptions(screen.getByLabelText("Step"), "cast_type");
    await userEvent.selectOptions(screen.getByLabelText("Column"), "id");
    await userEvent.selectOptions(screen.getByLabelText("Convert to"), "string");
    await userEvent.click(screen.getByRole("button", { name: "Add step" }));

    await userEvent.click(screen.getByRole("button", { name: /Run on version 1/ }));
    expect(await screen.findByRole("progressbar")).toHaveAttribute("aria-valuenow", "30");
    expect(calls.find((c) => c.key === CLEAN)?.body).toEqual({
      base_version: 1,
      operations: [{ op: "drop_duplicates", keep: "first" }, { op: "cast_type", column: "id", to: "string" }],
    });

    routes[DS] = [200, dataset({ versions: [version(1), version(2)] })];
    routes["GET /api/v1/jobs/c1"] = [200, job("c1", { job_type: "clean", status: "succeeded", progress: 100, result: { version: 2 } })];
    expect(await screen.findByText("Created version 2.")).toBeInTheDocument();
    expect(await screen.findByLabelText("Version")).toHaveValue("2");
    expect(screen.getByText("No steps yet.")).toBeInTheDocument();
  });

  it("shows why a cleaning job failed and keeps the steps for another try", async () => {
    setup("owner", {
      [CLEAN]: [202, job("c1", { job_type: "clean" })],
      "GET /api/v1/jobs/c1": [200, job("c1", { job_type: "clean", status: "failed", error_message: "Step 1 (drop_columns): Unknown column(s): zzz." })],
    });
    await openClean();
    await userEvent.click(screen.getByRole("button", { name: "Add step" }));
    await userEvent.click(screen.getByRole("button", { name: /Run on version 1/ }));
    expect(await screen.findByText("Step 1 (drop_columns): Unknown column(s): zzz.")).toBeInTheDocument();
    expect(screen.getByText("Remove duplicate rows, keep first")).toBeInTheDocument();
  });

  it("shows the server's message when the request is invalid", async () => {
    setup("owner", { [CLEAN]: [422, { error: { code: "validation_error", message: "The request is invalid." } }] });
    await openClean();
    await userEvent.click(screen.getByRole("button", { name: "Add step" }));
    await userEvent.click(screen.getByRole("button", { name: /Run on version 1/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The request is invalid.");
  });
});

describe("Export, roles and delete", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() }));
  });

  it("downloads the selected version with the user's token", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { calls } = setup("owner", {
      "GET /api/v1/datasets/d1/export": [200, "id,name\n1,a\n", { "Content-Disposition": 'attachment; filename="Sales_v1.csv"' }],
    });
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    await vi.waitFor(() => expect(click).toHaveBeenCalled());
    const call = calls.find((c) => c.key === "GET /api/v1/datasets/d1/export");
    expect(call?.url).toContain("version=1&format=csv");
    expect(call?.headers?.["Authorization"]).toBe("Bearer test-token");
    click.mockRestore();
  });

  it("tells the user when an export fails", async () => {
    setup("owner", { "GET /api/v1/datasets/d1/export": [500, {}] });
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("button", { name: "Download JSON" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The export failed.");
  });

  it("view-only users can read but see no way to change or delete", async () => {
    setup("viewer");
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("tab", { name: "Clean" }));
    expect(screen.getByText(/view-only access/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add step" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete dataset" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument();
  });

  it("members can clean but not delete", async () => {
    setup("member");
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("tab", { name: "Clean" }));
    expect(screen.getByRole("button", { name: "Add step" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete dataset" })).not.toBeInTheDocument();
  });

  it("owners delete only after confirming, then return to the project", async () => {
    const { calls } = setup("owner", {
      "DELETE /api/v1/datasets/d1": [204, null],
      "GET /api/v1/projects/p1/datasets": [200, { items: [], total: 0, limit: 50, offset: 0 }],
    });
    renderApp("/datasets/d1");
    await userEvent.click(await screen.findByRole("button", { name: "Delete dataset" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.key.startsWith("DELETE"))).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Delete dataset" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByRole("heading", { name: "Churn study" })).toBeInTheDocument();
    expect(calls.some((c) => c.key === "DELETE /api/v1/datasets/d1")).toBe(true);
  });
});
