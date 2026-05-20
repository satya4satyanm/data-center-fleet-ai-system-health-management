import { INACTIVE_AFTER_SEC } from '../config'
import type { FleetSystem } from '../types/metrics'

/** True when the system has reported within INACTIVE_AFTER_SEC (connected and sending data). */
export function isSystemActive(s: FleetSystem): boolean {
  if (s.last_seen_ago_sec != null) return s.last_seen_ago_sec <= INACTIVE_AFTER_SEC
  return s.online
}
