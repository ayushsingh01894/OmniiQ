import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getToken } from "../lib/session";
import { READY, ana, mockApi, renderApp } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const signedInRoutes = () => ({
  "GET /api/v1/auth/me": [200, ana] as [number, unknown],
  "GET /api/v1/health/ready": READY,
});

describe("app shell and routing", () => {
  it("shows the shell with the current user and Overview as the current page", async () => {
    mockApi(signedInRoutes());
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Ana")).toBeInTheDocument();
    expect(screen.getByText("ana@example.com")).toBeInTheDocument();
  });

  it("marks unbuilt modules as disabled instead of linking to them", async () => {
    mockApi(signedInRoutes());
    renderApp("/");
    const item = await screen.findByText("ML Lab");
    expect(item).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("link", { name: "ML Lab" })).not.toBeInTheDocument();
  });

  it("shows a not-found page with a way back for unknown routes", async () => {
    mockApi(signedInRoutes());
    renderApp("/does-not-exist");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Overview" })).toHaveAttribute("href", "/");
  });
});

describe("route protection", () => {
  it("sends signed-out visitors to the sign-in page without calling the API", async () => {
    const { calls } = mockApi({});
    renderApp("/projects", { signedIn: false });
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("signs the user out when the server rejects the token", async () => {
    mockApi({ "GET /api/v1/auth/me": [401, { error: { code: "unauthorized", message: "x" } }] });
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("offers a retry when the account can't be loaded for non-auth reasons", async () => {
    const { routes } = mockApi({
      "GET /api/v1/auth/me": "network-error",
      "GET /api/v1/health/ready": READY,
    });
    renderApp("/");
    expect(await screen.findByText("Can't reach OmniIQ")).toBeInTheDocument();
    expect(getToken()).toBe("test-token"); // a network blip must not log the user out

    routes["GET /api/v1/auth/me"] = [200, ana];
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it("signing out clears the token and returns to sign-in", async () => {
    mockApi(signedInRoutes());
    renderApp("/");
    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await waitFor(() => expect(getToken()).toBeNull());
  });
});
