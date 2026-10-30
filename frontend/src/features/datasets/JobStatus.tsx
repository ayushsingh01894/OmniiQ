import { useEffect, useRef } from "react";

import type { Job } from "../../lib/api";
import { isTerminal, useJob } from "./useJob";

const labels: Record<Job["job_type"], string> = {
  ingest: "Reading your file",
  profile: "Profiling",
  clean: "Applying cleaning steps",
};

export function JobStatus({
  jobId,
  onFinished,
}: {
  jobId: string;
  onFinished?: (job: Job) => void;
}) {
  const { data: job, isError } = useJob(jobId);
  const notified = useRef(false);

  useEffect(() => {
    if (job && isTerminal(job) && !notified.current) {
      notified.current = true;
      onFinished?.(job);
    }
  }, [job, onFinished]);

  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        Couldn&apos;t check the job&apos;s progress. Refresh the page to try again.
      </p>
    );
  }
  if (!job) return <p className="text-sm text-muted">Starting…</p>;

  if (job.status === "failed" || job.status === "cancelled") {
    return (
      <p role="alert" className="text-sm text-danger">
        {job.status === "cancelled" ? "This job was cancelled." : (job.error_message ?? "The job failed.")}
      </p>
    );
  }
  if (job.status === "succeeded") {
    return (
      <p role="status" className="text-sm text-accent">
        Finished.
      </p>
    );
  }
  return (
    <div role="status" className="space-y-1">
      <p className="text-sm">
        {job.status === "queued" ? "Waiting to start…" : `${labels[job.job_type]}…`}
      </p>
      <div
        role="progressbar"
        aria-label="Job progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={job.progress}
        className="h-1.5 w-full max-w-xs rounded-sm bg-line"
      >
        <div className="h-full rounded-sm bg-accent" style={{ width: `${job.progress}%` }} />
      </div>
    </div>
  );
}
