export const ACTIVE_JOB_KEY = 'pp_active_upload_job'
export const JOB_POLL_MS = 2500
/**
 * Sin ningun cambio (ni archivos, ni fase ETL, ni mensaje) tras N polls.
 * 240 * 2.5s ≈ 10 min — archivos grandes pueden tardar mas de 2 min en una sola fase.
 */
export const STALE_POLL_LIMIT = 240
