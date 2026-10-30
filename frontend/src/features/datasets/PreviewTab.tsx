import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "../../components/ui/Button";
import { getPreview } from "../../lib/api";

const PAGE = 25;

export function PreviewTab({ datasetId, version }: { datasetId: string; version: number }) {
  const [offset, setOffset] = useState(0);
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["preview", datasetId, version, offset],
    queryFn: () => getPreview(datasetId, version, offset, PAGE),
    placeholderData: keepPreviousData,
  });

  if (isPending) return <p role="status" className="text-muted">Loading rows…</p>;
  if (isError) {
    return (
      <div role="alert" className="space-y-2">
        <p>Couldn&apos;t load the rows.</p>
        <Button variant="secondary" onClick={() => void refetch()}>Try again</Button>
      </div>
    );
  }
  const last = Math.min(offset + data.rows.length, data.total_rows);

  return (
    <div className="space-y-3">
      <div className="max-w-full overflow-x-auto rounded-md border border-line bg-surface">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-line bg-paper">
            <tr>
              {data.columns.map((c) => (
                <th key={c.name} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">
                  {c.name} <span className="font-normal text-muted">{c.dtype}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.rows.map((row, i) => (
              <tr key={offset + i}>
                {data.columns.map((c) => {
                  const cell = row[c.name];
                  return (
                    <td key={c.name} className="whitespace-nowrap px-3 py-1.5">
                      {cell === null || cell === undefined ? <span className="text-muted">—</span> : String(cell)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          Previous
        </Button>
        <span aria-live="polite">
          Rows {data.total_rows === 0 ? 0 : offset + 1}–{last} of {data.total_rows.toLocaleString()}
        </span>
        <Button variant="secondary" disabled={last >= data.total_rows} onClick={() => setOffset(offset + PAGE)}>
          Next
        </Button>
      </div>
    </div>
  );
}
