import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getToken } from "../../lib/session";
import { READY, ana, mockApi, renderApp } from "../../test/render";

afterEach(() => vi.unstubAllGlobals());

const LOGIN = "POST /api/v1/auth/login";
const REGISTER = "POST /api/v1/auth/register";
const ME = "GET /api/v1/auth/me";
const HEALTH = "GET /api/v1/health/ready";
const TOKEN: [number, unknown] = [200, { access_token: "tok", token_type: "bearer", expires_in: 1800 }];

describe("LoginPage", () => {
  it("validates before calling the API", async () => {
    const { calls } = mockApi({});
    renderApp("/login", { signedIn: false });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("signs in and lands on the app", async () => {
    const { calls } = mockApi({ [LOGIN]: TOKEN, [ME]: [200, ana], [HEALTH]: READY });
    renderApp("/login", { signedIn: false });
    await userEvent.type(screen.getByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(getToken()).toBe("tok");
    expect(calls[0]).toMatchObject({
      key: LOGIN,
      body: { email: "ana@example.com", password: "correct horse battery" },
    });
  });

  it("shows a single generic message for bad credentials", async () => {
    mockApi({ [LOGIN]: [401, { error: { code: "invalid_credentials", message: "nope" } }] });
    renderApp("/login", { signedIn: false });
    await userEvent.type(screen.getByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(getToken()).toBeNull();
  });

  it("explains rate limiting", async () => {
    mockApi({ [LOGIN]: [429, { error: { code: "rate_limited", message: "x" } }] });
    renderApp("/login", { signedIn: false });
    await userEvent.type(screen.getByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/too many attempts/i);
  });

  it("links to registration", () => {
    mockApi({});
    renderApp("/login", { signedIn: false });
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", "/register");
  });
});

describe("RegisterPage", () => {
  it("rejects a short password client-side", async () => {
    const { calls } = mockApi({});
    renderApp("/register", { signedIn: false });
    await userEvent.type(screen.getByLabelText("Name"), "Ana");
    await userEvent.type(screen.getByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "short");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("shows an email error when the address is already registered", async () => {
    mockApi({ [REGISTER]: [409, { error: { code: "email_already_registered", message: "x" } }] });
    renderApp("/register", { signedIn: false });
    await userEvent.type(screen.getByLabelText("Name"), "Ana");
    await userEvent.type(screen.getByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
  });

  it("creates the account, signs in and lands on the app", async () => {
    const { calls } = mockApi({
      [REGISTER]: [201, ana],
      [LOGIN]: TOKEN,
      [ME]: [200, ana],
      [HEALTH]: READY,
    });
    renderApp("/register", { signedIn: false });
    await userEvent.type(screen.getByLabelText("Name"), "Ana");
    await userEvent.type(screen.getByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(calls.slice(0, 2).map((c) => c.key)).toEqual([REGISTER, LOGIN]);
  });
});
