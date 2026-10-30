import { useQuery } from "@tanstack/react-query";

import { getJob, type Job } from "../../lib/api";
import { JOB_POLL_MS } from "../../lib/config";

export const isTerminal = (job: Job | undefined) =>
  job !== undefined && ["succeeded", "failed", "cancelled"].includes(job.status);

/** Polls a job until it reaches a terminal state, then stops. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => (isTerminal(query.state.data) ? false : JOB_POLL_MS),
  });
}
