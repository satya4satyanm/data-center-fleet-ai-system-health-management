/** Must match agent push interval (server.py --interval). */
export const REFRESH_INTERVAL_MS = 10_000

/** Must match server.py STALE_AFTER_SEC — no data within this window → inactive. */
export const INACTIVE_AFTER_SEC = 30
