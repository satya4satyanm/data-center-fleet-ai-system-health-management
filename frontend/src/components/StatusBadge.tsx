import type { HealthStatus } from '../types/metrics'
import { statusColors, statusLabel } from '../lib/status'

export function StatusBadge({ status }: { status: HealthStatus }) {
  const c = statusColors(status)
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide font-mono ${c.bg} ${c.border} ${c.text}`}
    >
      {statusLabel(status)}
    </span>
  )
}
