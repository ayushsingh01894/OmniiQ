import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { useAuth } from "./AuthProvider";

export function RequireAuth() {
  const { status, retry, logout } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <p role="status" className="p-8 text-muted">
        Loading your workspace…
      </p>
    );
  }
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (status === "error") {
    return (
      <div role="alert" className="max-w-md space-y-3 p-8">
        <h1 className="text-xl font-semibold">Can&apos;t reach OmniIQ</h1>
        <p className="text-muted">
          We couldn&apos;t load your account. Check that the backend is running, then try again.
        </p>
        <div className="flex gap-2">
          <Button onClick={retry}>Try again</Button>
          <Button variant="secondary" onClick={logout}>
            Sign out
          </Button>
        </div>
      </div>
    );
  }
  return <Outlet />;
}
