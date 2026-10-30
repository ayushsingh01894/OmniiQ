// The access token lives in sessionStorage: it survives a page refresh but not closing the tab.
// Trade-off (documented in docs/security.md): script injected into the page could read it, so the
// app must stay free of XSS. httpOnly cookies are a possible later hardening.
const KEY = "omniiq.token";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null; // storage unavailable (e.g. blocked): behave as signed out
  }
}

export function storeToken(token: string): void {
  try {
    sessionStorage.setItem(KEY, token);
  } catch {
    // ignore: the user will simply have to sign in again after a refresh
  }
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
