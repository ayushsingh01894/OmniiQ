import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { TextField } from "../../components/forms/TextField";
import { Button } from "../../components/ui/Button";
import { ApiError, uploadDataset } from "../../lib/api";
import { MAX_UPLOAD_BYTES } from "../../lib/config";
import { JobStatus } from "./JobStatus";

export function UploadDatasetForm({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => uploadDataset(projectId, file, name),
    onSuccess: async ({ job }) => {
      setJobId(job.id);
      setName("");
      if (fileInput.current) fileInput.current.value = "";
      await queryClient.invalidateQueries({ queryKey: ["datasets", projectId] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "dataset_name_taken") {
        setFormError("A dataset with this name already exists in the project.");
      } else if (error instanceof ApiError && error.status < 500 && error.status !== 429) {
        setFormError(error.message);
      } else {
        setFormError("The upload failed. Check your connection and try again.");
      }
    },
  });

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    setJobId(null);
    const file = fileInput.current?.files?.[0];
    if (!file) return setFileError("Choose a .csv or .xlsx file.");
    if (!/\.(csv|xlsx)$/i.test(file.name)) return setFileError("Only .csv and .xlsx files are supported.");
    if (file.size > MAX_UPLOAD_BYTES) return setFileError("That file is larger than 25 MB.");
    setFileError(null);
    mutation.mutate(file);
  }

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-labelledby="upload-heading"
      className="max-w-md space-y-4 rounded-md border border-line bg-surface p-5"
    >
      <h2 id="upload-heading" className="text-base font-semibold">
        Upload a dataset
      </h2>
      <div className="space-y-1">
        <label htmlFor="dataset-file" className="block text-sm font-medium">
          File (.csv or .xlsx, up to 25 MB)
        </label>
        <input
          id="dataset-file"
          ref={fileInput}
          type="file"
          accept=".csv,.xlsx"
          aria-invalid={fileError ? true : undefined}
          aria-describedby={fileError ? "dataset-file-error" : undefined}
          className="block w-full text-sm"
        />
        {fileError ? (
          <p id="dataset-file-error" className="text-sm text-danger">
            {fileError}
          </p>
        ) : null}
      </div>
      <TextField
        label="Name (optional)"
        hint="Defaults to the file name."
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={120}
      />
      {formError ? (
        <p role="alert" className="text-sm text-danger">
          {formError}
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Uploading…" : "Upload"}
      </Button>
      {jobId ? (
        <JobStatus
          jobId={jobId}
          onFinished={() => void queryClient.invalidateQueries({ queryKey: ["datasets", projectId] })}
        />
      ) : null}
    </form>
  );
}
