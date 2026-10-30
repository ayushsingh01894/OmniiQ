import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { TextField } from "../../components/forms/TextField";
import { Button } from "../../components/ui/Button";
import {
  ApiError,
  requestCleaning,
  type DatasetVersion,
  type DType,
  type Job,
} from "../../lib/api";
import { buildOp, describeOp, emptyDraft, OP_LABELS, type CleaningOp, type Draft, type OpType } from "./cleaningOps";
import { JobStatus } from "./JobStatus";

const selectClass = "w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm";
const DTYPES: DType[] = ["string", "integer", "float", "boolean", "datetime"];

function ColumnPicker({
  legend,
  hint,
  names,
  value,
  onChange,
}: {
  legend: string;
  hint?: string;
  names: string[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <fieldset className="space-y-1">
      <legend className="text-sm font-medium">{legend}</legend>
      {hint ? <p className="text-sm text-muted">{hint}</p> : null}
      <div className="flex max-h-40 flex-wrap gap-x-4 gap-y-1 overflow-y-auto">
        {names.map((n) => (
          <label key={n} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={value.includes(n)}
              onChange={(e) => onChange(e.target.checked ? [...value, n] : value.filter((x) => x !== n))}
            />
            {n}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function CleanTab({
  datasetId,
  version,
  onCreated,
}: {
  datasetId: string;
  version: DatasetVersion;
  onCreated: (versionNumber: number) => void;
}) {
  const queryClient = useQueryClient();
  const names = version.columns.map((c) => c.name);
  const [draft, setDraft] = useState<Draft>(() => emptyDraft(names[0] ?? ""));
  const [steps, setSteps] = useState<CleaningOp[]>([]);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));

  const run = useMutation({
    mutationFn: () => requestCleaning(datasetId, { base_version: version.version, operations: steps }),
    onSuccess: (job) => {
      setJobId(job.id);
    },
    onError: (e) =>
      setRunError(e instanceof ApiError && e.status < 500 ? e.message : "Couldn't start the job. Try again."),
  });

  function addStep() {
    const built = buildOp(draft, version.columns);
    if ("error" in built) return setDraftError(built.error);
    setDraftError(null);
    setSteps((s) => [...s, built.op]);
  }

  function finished(job: Job) {
    void queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
    if (job.status === "succeeded") {
      setSteps([]);
      onCreated(Number(job.result?.["version"])); // the parent shows the confirmation (this tab remounts)
    }
  }

  const needsColumn = ["fill_missing", "rename_column", "cast_type"].includes(draft.type);
  const columnDtype = version.columns.find((c) => c.name === draft.column)?.dtype;

  return (
    <div className="space-y-6">
      <p className="max-w-prose text-sm text-muted">
        Build a list of steps and run them on version {version.version}. The result is saved as a new
        version; nothing is overwritten.
      </p>
      <div className="max-w-md space-y-4 rounded-md border border-line bg-surface p-5">
        <div className="space-y-1">
          <label htmlFor="op-type" className="block text-sm font-medium">
            Step
          </label>
          <select id="op-type" className={selectClass} value={draft.type} onChange={(e) => set("type", e.target.value as OpType)}>
            {(Object.keys(OP_LABELS) as OpType[]).map((t) => (
              <option key={t} value={t}>
                {OP_LABELS[t]}
              </option>
            ))}
          </select>
        </div>

        {needsColumn ? (
          <div className="space-y-1">
            <label htmlFor="op-column" className="block text-sm font-medium">
              Column
            </label>
            <select id="op-column" className={selectClass} value={draft.column} onChange={(e) => set("column", e.target.value)}>
              {names.map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </div>
        ) : null}

        {draft.type === "drop_duplicates" ? (
          <>
            <ColumnPicker legend="Compare only these columns" hint="Leave empty to compare whole rows." names={names} value={draft.columns} onChange={(v) => set("columns", v)} />
            <div className="space-y-1">
              <label htmlFor="op-keep" className="block text-sm font-medium">Keep</label>
              <select id="op-keep" className={selectClass} value={draft.keep} onChange={(e) => set("keep", e.target.value as "first" | "last")}>
                <option value="first">first occurrence</option>
                <option value="last">last occurrence</option>
              </select>
            </div>
          </>
        ) : null}

        {draft.type === "drop_missing" ? (
          <>
            <ColumnPicker legend="Look only at these columns" hint="Leave empty to look at every column." names={names} value={draft.columns} onChange={(v) => set("columns", v)} />
            <div className="space-y-1">
              <label htmlFor="op-how" className="block text-sm font-medium">Remove a row when</label>
              <select id="op-how" className={selectClass} value={draft.how} onChange={(e) => set("how", e.target.value as "any" | "all")}>
                <option value="any">any of those values is missing</option>
                <option value="all">all of those values are missing</option>
              </select>
            </div>
          </>
        ) : null}

        {draft.type === "trim_whitespace" ? (
          <ColumnPicker legend="Text columns" hint="Leave empty to trim every text column." names={names} value={draft.columns} onChange={(v) => set("columns", v)} />
        ) : null}

        {draft.type === "drop_columns" ? (
          <ColumnPicker legend="Columns to remove" names={names} value={draft.columns} onChange={(v) => set("columns", v)} />
        ) : null}

        {draft.type === "rename_column" ? (
          <TextField label="New name" value={draft.newName} onChange={(e) => set("newName", e.target.value)} maxLength={200} />
        ) : null}

        {draft.type === "cast_type" ? (
          <div className="space-y-1">
            <label htmlFor="op-to" className="block text-sm font-medium">Convert to</label>
            <select id="op-to" className={selectClass} value={draft.to} onChange={(e) => set("to", e.target.value as DType)}>
              {DTYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
        ) : null}

        {draft.type === "fill_missing" ? (
          <>
            <div className="space-y-1">
              <label htmlFor="op-strategy" className="block text-sm font-medium">Fill with</label>
              <select id="op-strategy" className={selectClass} value={draft.strategy} onChange={(e) => set("strategy", e.target.value as Draft["strategy"])}>
                <option value="mean">the average (numbers)</option>
                <option value="median">the median (numbers)</option>
                <option value="mode">the most common value</option>
                <option value="constant">a value I type</option>
              </select>
            </div>
            {draft.strategy === "constant" ? (
              columnDtype === "boolean" ? (
                <div className="space-y-1">
                  <label htmlFor="op-bool" className="block text-sm font-medium">Value</label>
                  <select id="op-bool" className={selectClass} value={draft.value} onChange={(e) => set("value", e.target.value)}>
                    <option value="">Choose…</option>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </div>
              ) : (
                <TextField label="Value" value={draft.value} onChange={(e) => set("value", e.target.value)} />
              )
            ) : null}
          </>
        ) : null}

        {draftError ? <p role="alert" className="text-sm text-danger">{draftError}</p> : null}
        <Button variant="secondary" onClick={addStep}>Add step</Button>
      </div>

      <section aria-labelledby="steps-heading" className="max-w-xl space-y-3">
        <h3 id="steps-heading" className="text-base font-semibold">Steps to run</h3>
        {steps.length === 0 ? (
          <p className="text-sm text-muted">No steps yet.</p>
        ) : (
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {steps.map((s, i) => (
              <li key={`${i}-${s.op}`}>
                <span>{describeOp(s as unknown as Record<string, unknown>)}</span>{" "}
                <button
                  type="button"
                  aria-label={`Remove step ${i + 1}`}
                  onClick={() => setSteps((all) => all.filter((_, j) => j !== i))}
                  className="text-accent underline underline-offset-2"
                >
                  Remove
                </button>
              </li>
            ))}
          </ol>
        )}
        {runError ? <p role="alert" className="text-sm text-danger">{runError}</p> : null}
        <Button
          disabled={steps.length === 0 || run.isPending}
          onClick={() => {
            setRunError(null);
            run.mutate();
          }}
        >
          {run.isPending ? "Starting…" : `Run on version ${version.version}`}
        </Button>
        {jobId ? <JobStatus key={jobId} jobId={jobId} onFinished={finished} /> : null}
      </section>
    </div>
  );
}
