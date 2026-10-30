import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import {
  ApiError,
  deleteDataset,
  downloadExport,
  getDataset,
  getProject,
  listJobs,
  listOrganizations,
} from "../../lib/api";
import { CleanTab } from "./CleanTab";
import { HistoryTab } from "./HistoryTab";
import { JobStatus } from "./JobStatus";
import { PreviewTab } from "./PreviewTab";
import { ProfileTab } from "./ProfileTab";

type Tab = "preview" | "profile" | "clean" | "history";
const TABS: { id: Tab; label: string }[] = [
  { id: "preview", label: "Preview" },
  { id: "profile", label: "Profile" },
  { id: "clean", label: "Clean" },
  { id: "history", label: "History" },
];

export function DatasetPage() {
  const { datasetId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("preview");
  const [chosen, setChosen] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const dataset = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => getDataset(datasetId),
    retry: false,
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 2000 : false),
  });
  const projectId = dataset.data?.project_id;
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId as string),
    enabled: projectId !== undefined,
  });
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: listOrganizations });
  const jobs = useQuery({
    queryKey: ["jobs", datasetId],
    queryFn: () => listJobs(datasetId),
    enabled: dataset.data !== undefined && dataset.data.status !== "ready",
  });

  const remove = useMutation({
    mutationFn: () => deleteDataset(datasetId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
      navigate(`/projects/${projectId}`);
    },
  });
  const exporter = useMutation({
    mutationFn: (format: "csv" | "json") => downloadExport(datasetId, selected?.version ?? 1, format),
    onSuccess: () => setExportError(null),
    onError: () => setExportError("The export failed. Try again."),
  });

  if (dataset.isPending || orgs.isPending) {
    return <p role="status" className="text-muted">Loading dataset…</p>;
  }
  if (dataset.isError) {
    const missing = dataset.error instanceof ApiError && dataset.error.status === 404;
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{missing ? "Dataset not found" : "Couldn't load this dataset"}</h1>
        <Link to="/projects" className="font-medium text-accent underline underline-offset-2">Back to projects</Link>
      </div>
    );
  }

  const d = dataset.data;
  const org = orgs.data?.find((o) => o.id === project.data?.organization_id);
  const canChange = org !== undefined && org.role !== "viewer";
  const canDelete = org?.role === "admin" || org?.role === "owner";
  const versions = [...d.versions].sort((a, b) => b.version - a.version);
  const selected = versions.find((v) => v.version === chosen) ?? versions[0];
  const latestJob = jobs.data?.[0];

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <Link to={`/projects/${d.project_id}`} className="text-sm text-accent underline underline-offset-2">
          {project.data?.name ?? "Project"}
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight">{d.name}</h1>
        <p className="text-sm text-muted">
          {d.original_filename} · {d.format.toUpperCase()} · {(d.original_size_bytes / 1024).toFixed(1)} KB
        </p>
      </header>

      {d.status === "processing" ? (
        <div className="max-w-md space-y-2">
          <h2 className="text-base font-semibold">We&apos;re reading your file</h2>
          {latestJob ? <JobStatus jobId={latestJob.id} /> : <p className="text-sm text-muted">Starting…</p>}
        </div>
      ) : null}

      {d.status === "failed" ? (
        <div role="alert" className="max-w-xl space-y-1 rounded-md border border-line bg-danger-soft px-4 py-3 text-danger">
          <p className="font-medium">This file couldn&apos;t be processed.</p>
          <p className="text-sm">
            {jobs.isPending ? "Loading details…" : (latestJob?.error_message ?? "Check the file and upload it again.")}
          </p>
          <p className="text-sm">Your original upload was kept unchanged.</p>
        </div>
      ) : null}

      {d.status === "ready" && selected ? (
        <>
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1">
              <label htmlFor="version-select" className="block text-sm font-medium">Version</label>
              <select
                id="version-select"
                value={selected.version}
                onChange={(e) => {
                  setChosen(Number(e.target.value));
                  setNotice(null);
                }}
                className="rounded-sm border border-line bg-surface px-3 py-2 text-sm"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.version}>
                    Version {v.version}
                    {v === versions[0] ? " (latest)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <Button variant="secondary" disabled={exporter.isPending} onClick={() => exporter.mutate("csv")}>
              Download CSV
            </Button>
            <Button variant="secondary" disabled={exporter.isPending} onClick={() => exporter.mutate("json")}>
              Download JSON
            </Button>
            {canDelete ? (
              confirmDelete ? (
                <span className="flex gap-2">
                  <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>Confirm delete</Button>
                  <Button variant="secondary" onClick={() => setConfirmDelete(false)}>Cancel</Button>
                </span>
              ) : (
                <Button variant="secondary" onClick={() => setConfirmDelete(true)}>Delete dataset</Button>
              )
            ) : null}
          </div>
          {notice ? (
            <p role="status" className="text-sm font-medium text-accent">
              {notice}
            </p>
          ) : null}
          {exportError ? <p role="alert" className="text-sm text-danger">{exportError}</p> : null}
          {remove.isError ? <p role="alert" className="text-sm text-danger">Couldn&apos;t delete this dataset.</p> : null}

          <div role="tablist" aria-label="Dataset sections" className="flex gap-1 border-b border-line">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                type="button"
                onClick={() => setTab(t.id)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                  tab === t.id ? "border-accent text-accent" : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "preview" ? <PreviewTab datasetId={d.id} version={selected.version} /> : null}
            {tab === "profile" ? <ProfileTab datasetId={d.id} version={selected.version} /> : null}
            {tab === "history" ? <HistoryTab versions={d.versions} /> : null}
            {tab === "clean" ? (
              canChange ? (
                <CleanTab key={selected.version} datasetId={d.id} version={selected} onCreated={(n) => {
                    setChosen(n);
                    setNotice(`Created version ${n}.`);
                  }} />
              ) : (
                <p className="text-sm text-muted">You have view-only access, so you can&apos;t change this dataset.</p>
              )
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
