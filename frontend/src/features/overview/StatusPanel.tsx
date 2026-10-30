import { useQuery } from "@tanstack/react-query";

import { getReadiness } from "../../lib/api";

type Tone = "ok" | "warn" | "bad" | "idle";

const toneClass: Record<Tone, string> = {
  ok: "bg-accent-soft text-accent",
  warn: "bg-warn-soft text-warn",
  bad: "bg-danger-soft text-danger",
  idle: "bg-line text-muted",
};

function Row({ name, label, tone }: { name: string; label: string; tone: Tone }) {
  return (
    <div className="flex items-center justify-between py-3">
      <dt className="text-sm text-muted">{name}</dt>
      <dd className={`rounded-sm px-2 py-0.5 text-sm font-medium ${toneClass[tone]}`}>{label}</dd>
    </div>
  );
}

export function StatusPanel() {
  const query = useQuery({
    queryKey: ["health", "ready"],
    queryFn: getReadiness,
    retry: false,
    refetchInterval: 15_000,
  });

  let api: { label: string; tone: Tone };
  let database: { label: string; tone: Tone };
  let note: string | null = null;

  if (query.isPending) {
    api = { label: "Checking", tone: "idle" };
    database = { label: "Checking", tone: "idle" };
  } else if (query.isError) {
    api = { label: "Unreachable", tone: "bad" };
    database = { label: "Unknown", tone: "idle" };
    note = "The API did not respond. Check that the backend is running, then retry.";
  } else if (query.data.database === "down") {
    api = { label: "Running", tone: "ok" };
    database = { label: "Down", tone: "bad" };
    note = "The API is running but cannot reach its database.";
  } else {
    api = { label: "Running", tone: "ok" };
    database = { label: "Connected", tone: "ok" };
  }

  return (
    <section aria-labelledby="status-heading" className="max-w-md rounded-md border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 id="status-heading" className="text-base font-semibold">
          System status
        </h2>
        <button
          type="button"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
          className="rounded-sm px-2 py-1 text-sm font-medium text-accent hover:bg-accent-soft disabled:opacity-50"
        >
          {query.isFetching ? "Checking…" : "Check again"}
        </button>
      </div>
      <dl className="divide-y divide-line px-5">
        <Row name="API" label={api.label} tone={api.tone} />
        <Row name="Database" label={database.label} tone={database.tone} />
      </dl>
      {note ? (
        <p role="status" className="border-t border-line px-5 py-3 text-sm text-muted">
          {note}
        </p>
      ) : null}
    </section>
  );
}
