import { useQuery } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { getProfile, type ProfileColumn } from "../../lib/api";

const fmt = (v: unknown) => (typeof v === "number" ? Number(v.toPrecision(6)).toString() : String(v ?? "—"));

function summary(c: ProfileColumn): string {
  if (c.stats && "mean" in c.stats) return `min ${fmt(c.stats["min"])} · mean ${fmt(c.stats["mean"])} · max ${fmt(c.stats["max"])}`;
  if (c.stats) return `${String(c.stats["min"]).slice(0, 10)} to ${String(c.stats["max"]).slice(0, 10)}`;
  if (c.top_values?.length) return c.top_values.slice(0, 3).map((t) => `${t.value} (${t.count})`).join(", ");
  return "—";
}

export function ProfileTab({ datasetId, version }: { datasetId: string; version: number }) {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["profile", datasetId, version],
    queryFn: () => getProfile(datasetId, version),
  });

  if (isPending) return <p role="status" className="text-muted">Loading profile…</p>;
  if (isError) {
    return (
      <div role="alert" className="space-y-2">
        <p>Couldn&apos;t load the data profile for this version.</p>
        <Button variant="secondary" onClick={() => void refetch()}>Try again</Button>
      </div>
    );
  }

  const facts: [string, string][] = [
    ["Rows", data.row_count.toLocaleString()],
    ["Columns", String(data.column_count)],
    ["Duplicate rows", data.duplicate_rows.toLocaleString()],
    ["Missing cells", data.missing_cells.toLocaleString()],
  ];

  return (
    <div className="space-y-6">
      <dl className="grid max-w-xl grid-cols-2 gap-3 sm:grid-cols-4">
        {facts.map(([k, v]) => (
          <div key={k} className="rounded-md border border-line bg-surface px-3 py-2">
            <dt className="text-sm text-muted">{k}</dt>
            <dd className="text-lg font-semibold">{v}</dd>
          </div>
        ))}
      </dl>

      <section aria-labelledby="issues-heading" className="max-w-2xl">
        <h3 id="issues-heading" className="mb-2 text-base font-semibold">Data quality</h3>
        {data.issues.length === 0 ? (
          <p className="text-sm text-muted">No issues found.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {data.issues.map((issue, i) => (
              <li key={i} className="rounded-sm bg-warn-soft px-3 py-1.5 text-warn">
                {issue.column ? <strong>{issue.column}: </strong> : null}
                {issue.message}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="columns-heading">
        <h3 id="columns-heading" className="mb-2 text-base font-semibold">Columns</h3>
        <div className="max-w-full overflow-x-auto rounded-md border border-line bg-surface">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line bg-paper">
              <tr>
                {["Column", "Type", "Missing", "Distinct", "Summary"].map((h) => (
                  <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.columns.map((c) => (
                <tr key={c.name}>
                  <th scope="row" className="px-3 py-1.5 font-medium">{c.name}</th>
                  <td className="px-3 py-1.5">{c.dtype}</td>
                  <td className="px-3 py-1.5">{c.missing} ({c.missing_pct}%)</td>
                  <td className="px-3 py-1.5">{c.unique}</td>
                  <td className="px-3 py-1.5 text-muted">{summary(c)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
