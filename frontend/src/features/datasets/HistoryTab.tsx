import type { DatasetVersion } from "../../lib/api";
import { describeOp } from "./cleaningOps";

export function HistoryTab({ versions }: { versions: DatasetVersion[] }) {
  const newestFirst = [...versions].sort((a, b) => b.version - a.version);
  return (
    <ol className="max-w-2xl space-y-3">
      {newestFirst.map((v) => (
        <li key={v.id} className="rounded-md border border-line bg-surface px-4 py-3">
          <p className="font-medium">
            Version {v.version}{" "}
            <span className="font-normal text-muted">
              · {v.parent_version ? `from version ${v.parent_version}` : "original upload"} ·{" "}
              {v.row_count.toLocaleString()} rows × {v.column_count} columns ·{" "}
              {new Date(v.created_at).toLocaleDateString()}
            </span>
          </p>
          {v.operations?.length ? (
            <ul className="mt-1 list-disc pl-5 text-sm text-muted">
              {v.operations.map((op, i) => (
                <li key={i}>{describeOp(op)}</li>
              ))}
            </ul>
          ) : null}
          <p className="mt-1 break-all text-xs text-muted">SHA-256 {v.checksum_sha256}</p>
        </li>
      ))}
    </ol>
  );
}
