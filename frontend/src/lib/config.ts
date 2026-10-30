/** How often running jobs are re-checked (short in tests so they stay fast). */
export const JOB_POLL_MS = import.meta.env.MODE === "test" ? 20 : 1500;
/** Mirrors the backend default. The server is the real authority; this only avoids a pointless upload. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
