import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthProvider";

/** Centered card for sign-in / sign-up. Signed-in users are sent on to the app. */
export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (status === "authenticated") return <Navigate to={from} replace />;

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div>
          <p className="text-xl font-semibold tracking-tight text-accent">OmniIQ</p>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">{title}</h1>
        </div>
        <div className="rounded-md border border-line bg-surface p-5">{children}</div>
      </div>
    </div>
  );
}
