import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getProject, listDatasets, listOrganizations, type DatasetStatus } from "../../lib/api";
import { UploadDatasetForm } from "./UploadDatasetForm";

const statusLabel: Record<DatasetStatus, { text: string; cls: string }> = {
  processing: { text: "Processing", cls: "bg-warn-soft text-warn" },
  ready: { text: "Ready", cls: "bg-accent-soft text-accent" },
  failed: { text: "Failed", cls: "bg-danger-soft text-danger" },
};

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId) });
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: listOrganizations });
  const datasets = useQuery({
    queryKey: ["datasets", projectId],
    queryFn: () => listDatasets(projectId),
    // keep refreshing while anything is still being processed
    refetchInterval: (q) => (q.state.data?.items.some((d) => d.status === "processing") ? 2000 : false),
  });

  if (project.isPending || orgs.isPending || datasets.isPending) {
    return (
      <p role="status" className="text-muted">
        Loading project…
      </p>
    );
  }
  if (project.isError) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Project not found</h1>
        <Link to="/projects" className="font-medium text-accent underline underline-offset-2">
          Back to projects
        </Link>
      </div>
    );
  }
  if (orgs.isError || datasets.isError) {
    return <p role="alert">Couldn&apos;t load this project&apos;s datasets. Refresh to try again.</p>;
  }

  const role = orgs.data.find((o) => o.id === project.data.organization_id)?.role;
  const canUpload = role !== undefined && role !== "viewer";
  const { items, total } = datasets.data;

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <Link to="/projects" className="text-sm text-accent underline underline-offset-2">
          Projects
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight">{project.data.name}</h1>
        {project.data.description ? <p className="text-muted">{project.data.description}</p> : null}
      </header>

      {canUpload ? (
        <UploadDatasetForm projectId={projectId} />
      ) : (
        <p className="max-w-md text-sm text-muted">You have view-only access, so you can&apos;t upload.</p>
      )}

      <section aria-labelledby="datasets-heading" className="max-w-2xl">
        <h2 id="datasets-heading" className="mb-2 text-base font-semibold">
          Datasets
        </h2>
        {items.length === 0 ? (
          <p className="rounded-md border border-dashed border-line px-5 py-8 text-muted">
            No datasets yet.{canUpload ? " Upload a CSV or Excel file above." : ""}
          </p>
        ) : (
          <>
            <ul className="divide-y divide-line rounded-md border border-line bg-surface">
              {items.map((d) => {
                const badge = statusLabel[d.status];
                return (
                  <li key={d.id} className="flex items-center justify-between gap-4 px-5 py-4">
                    <div className="min-w-0">
                      <Link to={`/datasets/${d.id}`} className="font-medium text-accent underline underline-offset-2">
                        {d.name}
                      </Link>
                      <p className="text-sm text-muted">
                        {d.latest_version
                          ? `${d.latest_version.row_count.toLocaleString()} rows × ${d.latest_version.column_count} columns · version ${d.latest_version.version}`
                          : d.original_filename}
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-sm px-2 py-0.5 text-sm font-medium ${badge.cls}`}>
                      {badge.text}
                    </span>
                  </li>
                );
              })}
            </ul>
            {total > items.length ? (
              <p className="mt-2 text-sm text-muted">
                Showing the first {items.length} of {total} datasets.
              </p>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}
