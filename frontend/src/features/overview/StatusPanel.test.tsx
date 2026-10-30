import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { READY, ana, mockApi, renderApp } from "../../test/render";

afterEach(() => vi.unstubAllGlobals());

const ME = "GET /api/v1/auth/me";
const HEALTH = "GET /api/v1/health/ready";

describe("StatusPanel", () => {
  it("shows a checking state before the first response", async () => {
    mockApi({ [ME]: [200, ana], [HEALTH]: "pending" });
    renderApp("/");
    expect(await screen.findAllByText("Checking")).toHaveLength(2);
  });

  it("shows API running and database connected when ready", async () => {
    mockApi({ [ME]: [200, ana], [HEALTH]: READY });
    renderApp("/");
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("shows database down (not API down) when the API returns 503", async () => {
    mockApi({ [ME]: [200, ana], [HEALTH]: [503, { status: "not_ready", database: "down" }] });
    renderApp("/");
    expect(await screen.findByText("Down")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/cannot reach its database/i);
  });

  it("shows an actionable error when the API is unreachable, and can retry", async () => {
    const { routes } = mockApi({ [ME]: [200, ana], [HEALTH]: "network-error" });
    renderApp("/");
    expect(await screen.findByText("Unreachable")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/backend is running/i);

    routes[HEALTH] = READY;
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });
});
