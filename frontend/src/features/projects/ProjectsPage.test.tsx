import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ana, mockApi, org, project, renderApp, type Routes } from "../../test/render";

afterEach(() => vi.unstubAllGlobals());

const ME = "GET /api/v1/auth/me";
const ORGS = "GET /api/v1/organizations";
const LIST = "GET /api/v1/projects";
const page = (items: ReturnType<typeof project>[], total = items.length) =>
  [200, { items, total, limit: 50, offset: 0 }] as [number, unknown];

function setup(extra: Routes) {
  return mockApi({ [ME]: [200, ana], ...extra });
}

describe("ProjectsPage", () => {
  it("lists projects with their organization and offers delete only to admins and owners", async () => {
    setup({
      [ORGS]: [200, [org("a", "Alpha Org", "owner"), org("b", "Beta Org", "viewer"), org("c", "Gamma Org", "member")]],
      [LIST]: page([project("1", "In Alpha", "a"), project("2", "In Beta", "b"), project("3", "In Gamma", "c")]),
    });
    renderApp("/projects");
    expect(await screen.findByText("In Alpha")).toBeInTheDocument();
    expect(screen.getByText(/Beta Org/)).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Delete In Alpha" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete In Beta" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete In Gamma" })).not.toBeInTheDocument();
  });

  it("only offers organizations where the user can create projects", async () => {
    setup({
      [ORGS]: [200, [org("a", "Alpha Org", "owner"), org("b", "Beta Org", "viewer")]],
      [LIST]: page([]),
    });
    renderApp("/projects");
    const select = await screen.findByLabelText("Organization");
    const names = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(names).toEqual(["Alpha Org"]);
  });

  it("hides the create form for view-only users and says why", async () => {
    setup({ [ORGS]: [200, [org("b", "Beta Org", "viewer")]], [LIST]: page([]) });
    renderApp("/projects");
    expect(await screen.findByText(/view-only access/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create project" })).not.toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    setup({ [ORGS]: [200, [org("a", "Alpha Org", "owner")]], [LIST]: page([]) });
    renderApp("/projects");
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it("validates the name before calling the API", async () => {
    const { calls } = setup({ [ORGS]: [200, [org("a", "Alpha Org", "owner")]], [LIST]: page([]) });
    renderApp("/projects");
    await userEvent.click(await screen.findByRole("button", { name: "Create project" }));
    expect(await screen.findByText("Enter a project name.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/v1/projects")).toBe(false);
  });

  it("creates a project and refreshes the list", async () => {
    const { routes, calls } = setup({
      [ORGS]: [200, [org("a", "Alpha Org", "owner")]],
      [LIST]: page([]),
      "POST /api/v1/projects": [201, project("9", "Fresh", "a")],
    });
    renderApp("/projects");
    await userEvent.type(await screen.findByLabelText("Name"), "  Fresh  ");
    routes[LIST] = page([project("9", "Fresh", "a")]);
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(await screen.findByRole("button", { name: "Delete Fresh" })).toBeInTheDocument();
    const post = calls.find((c) => c.key === "POST /api/v1/projects");
    expect(post?.body).toEqual({ organization_id: "a", name: "Fresh" });
    expect(screen.getByLabelText("Name")).toHaveValue(""); // form reset
  });

  it("shows a field error for a duplicate project name", async () => {
    setup({
      [ORGS]: [200, [org("a", "Alpha Org", "owner")]],
      [LIST]: page([]),
      "POST /api/v1/projects": [409, { error: { code: "project_name_taken", message: "x" } }],
    });
    renderApp("/projects");
    await userEvent.type(await screen.findByLabelText("Name"), "Dup");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText(/already exists there/)).toBeInTheDocument();
  });

  it("requires confirmation before deleting, and can be cancelled", async () => {
    const { calls } = setup({
      [ORGS]: [200, [org("a", "Alpha Org", "owner")]],
      [LIST]: page([project("1", "Doomed", "a")]),
      "DELETE /api/v1/projects/1": [204, null],
    });
    renderApp("/projects");
    await userEvent.click(await screen.findByRole("button", { name: "Delete Doomed" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.key.startsWith("DELETE"))).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Delete Doomed" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(calls.some((c) => c.key === "DELETE /api/v1/projects/1")).toBe(true);
  });

  it("shows an error state with retry when loading fails", async () => {
    const { routes } = setup({ [ORGS]: [200, [org("a", "Alpha Org", "owner")]], [LIST]: [500, {}] });
    renderApp("/projects");
    expect(await screen.findByText("Couldn't load your projects.")).toBeInTheDocument();
    routes[LIST] = page([project("1", "Back", "a")]);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Back")).toBeInTheDocument();
  });

  it("tells the user when the list is truncated", async () => {
    setup({
      [ORGS]: [200, [org("a", "Alpha Org", "owner")]],
      [LIST]: page([project("1", "Only", "a")], 120),
    });
    renderApp("/projects");
    expect(await screen.findByText("Showing the first 1 of 120 projects.")).toBeInTheDocument();
  });
});
