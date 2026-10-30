import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import {
  deleteProject,
  listOrganizations,
  listProjects,
  type Organization,
  type Project,
} from "../../lib/api";
import { CreateProjectForm } from "./CreateProjectForm";

function ProjectRow({ project, org }: { project: Project; org: Organization | undefined }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const canDelete = org?.role === "admin" || org?.role === "owner";

  const remove = useMutation({
    mutationFn: () => deleteProject(project.id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  return (
    <li className="flex items-start justify-between gap-4 px-5 py-4">
      <div className="min-w-0">
        <Link
          to={`/projects/${project.id}`}
          className="font-medium text-accent underline underline-offset-2"
        >
          {project.name}
        </Link>
        <p className="text-sm text-muted">
          {org?.name ?? "Unknown organization"} · created{" "}
          {new Date(project.created_at).toLocaleDateString()}
        </p>
        {project.description ? <p className="mt-1 text-sm">{project.description}</p> : null}
        {remove.isError ? (
          <p role="alert" className="mt-1 text-sm text-danger">
            Couldn&apos;t delete this project. It may already be gone, or your role can&apos;t
            delete it.
          </p>
        ) : null}
      </div>
      {canDelete ? (
        confirming ? (
          <div className="flex shrink-0 gap-2">
            <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
              Confirm delete
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            variant="secondary"
            aria-label={`Delete ${project.name}`}
            onClick={() => setConfirming(true)}
          >
            Delete
          </Button>
        )
      ) : null}
    </li>
  );
}

export function ProjectsPage() {
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: listOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });

  if (orgs.isPending || projects.isPending) {
    return (
      <p role="status" className="text-muted">
        Loading projects…
      </p>
    );
  }
  if (orgs.isError || projects.isError) {
    return (
      <div role="alert" className="space-y-3">
        <p>Couldn&apos;t load your projects.</p>
        <Button
          variant="secondary"
          onClick={() => {
            void orgs.refetch();
            void projects.refetch();
          }}
        >
          Try again
        </Button>
      </div>
    );
  }

  const orgById = new Map(orgs.data.map((o) => [o.id, o]));
  const writable = orgs.data.filter((o) => o.role !== "viewer");
  const { items, total } = projects.data;

  return (
    <div className="space-y-8">
      <header className="max-w-prose space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
        <p className="text-muted">
          A project holds the datasets, analyses and models for one piece of work. Open one to upload
          and clean datasets.
        </p>
      </header>

      {writable.length > 0 ? (
        <CreateProjectForm organizations={writable} />
      ) : (
        <p className="max-w-md text-sm text-muted">
          You have view-only access, so you can&apos;t create projects.
        </p>
      )}

      <section aria-labelledby="project-list-heading" className="max-w-2xl">
        <h2 id="project-list-heading" className="mb-2 text-base font-semibold">
          Your projects
        </h2>
        {items.length === 0 ? (
          <p className="rounded-md border border-dashed border-line px-5 py-8 text-muted">
            No projects yet.{writable.length > 0 ? " Create your first one above." : ""}
          </p>
        ) : (
          <>
            <ul className="divide-y divide-line rounded-md border border-line bg-surface">
              {items.map((p) => (
                <ProjectRow key={p.id} project={p} org={orgById.get(p.organization_id)} />
              ))}
            </ul>
            {total > items.length ? (
              <p className="mt-2 text-sm text-muted">
                Showing the first {items.length} of {total} projects.
              </p>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}
