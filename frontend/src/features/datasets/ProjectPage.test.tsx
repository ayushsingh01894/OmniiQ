import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ana, dataset, job, mockApi, org, project, renderApp, version, type Routes } from "../../test/render";

afterEach(() => vi.unstubAllGlobals());

const ME = "GET /api/v1/auth/me";
const ORGS = "GET /api/v1/organizations";
const PROJ = "GET /api/v1/projects/p1";
const LIST = "GET /api/v1/projects/p1/datasets";
const UPLOAD = "POST /api/v1/projects/p1/datasets";
const JOB = "GET /api/v1/jobs/j1";

const page = (items: ReturnType<typeof dataset>[]) => [200, { items, total: items.length, limit: 50, offset: 0 }] as [number, unknown];

function setup(role: "owner" | "viewer" = "owner", extra: Routes = {}) {
  return mockApi({
    [ME]: [200, ana],
    [ORGS]: [200, [org("o1", "Acme", role)]],
    [PROJ]: [200, project("p1", "Churn study", "o1")],
    [LIST]: page([]),
    ...extra,
  });
}

describe("ProjectPage", () => {
  it("lists datasets with status and size, linking to each one", async () => {
    setup("owner", {
      [LIST]: page([
        dataset({ id: "d1", name: "Sales", versions: [version(1), version(2, { row_count: 1200, column_count: 7 })] }),
        dataset({ id: "d2", name: "Broken", status: "failed", versions: [], latest_version: null }),
      ]),
    });
    renderApp("/projects/p1");
    expect(await screen.findByRole("heading", { name: "Churn study" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sales" })).toHaveAttribute("href", "/datasets/d1");
    expect(screen.getByText(/1,200 rows × 7 columns · version 2/)).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    setup();
    renderApp("/projects/p1");
    expect(await screen.findByText(/No datasets yet/)).toBeInTheDocument();
  });

  it("hides the upload form for view-only users", async () => {
    setup("viewer");
    renderApp("/projects/p1");
    expect(await screen.findByText(/view-only access/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload" })).not.toBeInTheDocument();
  });

  it("shows a not-found page for a project you can't open", async () => {
    setup("owner", { [PROJ]: [404, { error: { code: "project_not_found", message: "x" } }] });
    renderApp("/projects/p1");
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
  });
});

describe("UploadDatasetForm", () => {
  const csv = () => new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" });

  it("checks the file before uploading anything", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const { calls } = setup();
    renderApp("/projects/p1");
    await screen.findByRole("button", { name: "Upload" });

    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("Choose a .csv or .xlsx file.")).toBeInTheDocument();

    await user.upload(screen.getByLabelText(/File \(/), new File(["x"], "notes.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("Only .csv and .xlsx files are supported.")).toBeInTheDocument();

    expect(calls.some((c) => c.key === UPLOAD)).toBe(false);
  });

  it("uploads, shows job progress, and refreshes the list when done", async () => {
    const { routes, calls } = setup("owner", {
      [UPLOAD]: [202, { dataset: dataset({ status: "processing", versions: [], latest_version: null }), job: job("j1") }],
      [JOB]: [200, job("j1", { status: "running", progress: 40 })],
    });
    renderApp("/projects/p1");
    await userEvent.upload(await screen.findByLabelText(/File \(/), csv());
    await userEvent.type(screen.getByLabelText("Name (optional)"), "  My data ");
    routes[LIST] = page([dataset({ name: "My data" })]);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));

    const bar = await screen.findByRole("progressbar", { name: "Job progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "40");

    routes[JOB] = [200, job("j1", { status: "succeeded", progress: 100 })];
    expect(await screen.findByText("Finished.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "My data" })).toBeInTheDocument();

    const post = calls.find((c) => c.key === UPLOAD);
    expect(post?.body).toMatchObject({ name: "My data" });
    expect((post?.body as { file: File }).file.name).toBe("data.csv");
    expect(post?.headers?.["Content-Type"]).toBeUndefined(); // browser must set the multipart boundary
    expect(post?.headers?.["Authorization"]).toBe("Bearer test-token");
  });

  it("shows the server's reason when the file is rejected", async () => {
    setup("owner", { [UPLOAD]: [422, { error: { code: "invalid_file_content", message: "CSV files must be UTF-8 encoded." } }] });
    renderApp("/projects/p1");
    await userEvent.upload(await screen.findByLabelText(/File \(/), csv());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("CSV files must be UTF-8 encoded.");
  });

  it("explains a duplicate name", async () => {
    setup("owner", { [UPLOAD]: [409, { error: { code: "dataset_name_taken", message: "x" } }] });
    renderApp("/projects/p1");
    await userEvent.upload(await screen.findByLabelText(/File \(/), csv());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/already exists in the project/);
  });

  it("shows a failed ingest job's reason", async () => {
    setup("owner", {
      [UPLOAD]: [202, { dataset: dataset({ status: "processing", versions: [], latest_version: null }), job: job("j1") }],
      [JOB]: [200, job("j1", { status: "failed", error_message: "The file has more than 500,000 rows." })],
    });
    renderApp("/projects/p1");
    await userEvent.upload(await screen.findByLabelText(/File \(/), csv());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("The file has more than 500,000 rows.")).toBeInTheDocument();
  });
});
