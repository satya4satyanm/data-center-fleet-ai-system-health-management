import { Link } from 'react-router-dom'
import type { FleetSystem } from '../types/metrics'
import { isSystemActive } from '../lib/fleet'
import { timeAgo } from '../lib/format'
import { statusColors } from '../lib/status'
import { StatusBadge } from './StatusBadge'

export function SystemCard({ system }: { system: FleetSystem }) {
  const online = isSystemActive(system)
  const c = statusColors(online ? system.status : 'offline')

  return (
    <Link
      to={`/systems/${encodeURIComponent(system.id)}`}
      className={`group relative block overflow-hidden rounded-xl border bg-[var(--color-surface)] p-4 transition hover:border-white/15 ${c.border}`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${c.bar}`} />
      <div className="flex items-start justify-between gap-2 pl-2">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-sm font-semibold text-white group-hover:text-[var(--color-ok)]">
            {system.hostname}
          </h3>
          <p className="mt-0.5 truncate text-[11px] text-[var(--color-muted)]">
            {system.os} {system.os_release} · {system.machine}
          </p>
        </div>
        <StatusBadge status={online ? system.status : 'offline'} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 pl-2 text-center">
        <MetricMini label="CPU" value={system.cpu_pct != null ? `${system.cpu_pct}%` : '—'} />
        <MetricMini label="RAM" value={system.memory_pct != null ? `${system.memory_pct}%` : '—'} />
        <MetricMini label="Load" value={system.load_avg_1m != null ? String(system.load_avg_1m) : '—'} />
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--color-border)] pt-3 pl-2 text-[10px] text-[var(--color-muted)]">
        <span className="flex items-center gap-1.5">
          {online ? (
            <>
              <span className={`h-1.5 w-1.5 rounded-full ${c.dot} animate-pulse-dot`} />
              Online
            </>
          ) : (
            <>Offline</>
          )}
        </span>
        <span>{timeAgo(system.last_seen_ago_sec)}</span>
        {system.alert_count ? (
          <span className="rounded bg-[var(--color-warn)]/15 px-1.5 py-0.5 text-[var(--color-warn)]">
            {system.alert_count} alert{system.alert_count > 1 ? 's' : ''}
          </span>
        ) : null}
      </div>

      {Object.keys(system.tags).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1 pl-2">
          {Object.entries(system.tags).map(([k, v]) => (
            <span
              key={k}
              className="rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--color-muted)]"
            >
              {k}={v}
            </span>
          ))}
        </div>
      )}
    </Link>
  )
}

function MetricMini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[var(--color-surface-2)] px-2 py-2">
      <div className="text-[9px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      <div className="font-mono text-sm font-semibold text-white">{value}</div>
    </div>
  )
}
