import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { TextField } from "../../components/forms/TextField";
import { Button } from "../../components/ui/Button";
import { ApiError, createProject, type Organization } from "../../lib/api";

const schema = z.object({
  organization_id: z.string().min(1, "Choose an organization."),
  name: z.string().trim().min(1, "Enter a project name.").max(120, "Use 120 characters or fewer."),
  description: z.string().trim().max(2000, "Use 2000 characters or fewer."),
});
type Values = z.infer<typeof schema>;

export function CreateProjectForm({ organizations }: { organizations: Organization[] }) {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const first = organizations[0];
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { organization_id: first?.id ?? "", name: "", description: "" },
  });

  const mutation = useMutation({
    mutationFn: (v: Values) =>
      createProject({
        organization_id: v.organization_id,
        name: v.name,
        ...(v.description ? { description: v.description } : {}),
      }),
    onSuccess: async (_, v) => {
      reset({ organization_id: v.organization_id, name: "", description: "" });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "project_name_taken") {
        setError("name", { message: "A project with this name already exists there." });
      } else if (error instanceof ApiError && error.status === 403) {
        setFormError("Your role in that organization can't create projects.");
      } else {
        setFormError("Couldn't create the project. Try again.");
      }
    },
  });

  return (
    <form
      onSubmit={handleSubmit((v) => {
        setFormError(null);
        mutation.mutate(v);
      })}
      noValidate
      aria-labelledby="new-project-heading"
      className="max-w-md space-y-4 rounded-md border border-line bg-surface p-5"
    >
      <h2 id="new-project-heading" className="text-base font-semibold">
        New project
      </h2>
      <div className="space-y-1">
        <label htmlFor="project-org" className="block text-sm font-medium">
          Organization
        </label>
        <select
          id="project-org"
          className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm"
          {...register("organization_id")}
        >
          {organizations.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
        {errors.organization_id ? (
          <p className="text-sm text-danger">{errors.organization_id.message}</p>
        ) : null}
      </div>
      <TextField label="Name" error={errors.name?.message} {...register("name")} />
      <TextField
        label="Description (optional)"
        error={errors.description?.message}
        {...register("description")}
      />
      {formError ? (
        <p role="alert" className="text-sm text-danger">
          {formError}
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Creating…" : "Create project"}
      </Button>
    </form>
  );
}
