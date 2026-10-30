import { StatusPanel } from "./StatusPanel";

export function OverviewPage() {
  return (
    <div className="space-y-8">
      <header className="max-w-prose space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="text-muted">
          You can sign in and organise work into projects. Datasets and analysis arrive in the next phase; until
          then this page shows whether the backend is healthy.
        </p>
      </header>
      <StatusPanel />
    </div>
  );
}
