import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="max-w-prose space-y-3">
      <h1 className="text-3xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-muted">That address doesn&apos;t match anything in OmniIQ.</p>
      <Link to="/" className="font-medium text-accent underline underline-offset-2">
        Go to Overview
      </Link>
    </div>
  );
}
