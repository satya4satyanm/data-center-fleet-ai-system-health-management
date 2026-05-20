import { useCallback, useMemo } from 'react'
import { fetchFleet } from '../api/client'
import { INACTIVE_AFTER_SEC } from '../config'
import { SystemCard } from '../components/SystemCard'
import type { FleetSystem } from '../types/metrics'
import { usePolling } from '../hooks/usePolling'
import { isSystemActive } from '../lib/fleet'
import { statusColors } from '../lib/status'

export function FleetPage() {
  const load = useCallback(() => fetchFleet(), [])
  const { data, error, loading } = usePolling(load)

  const { activeSystems, inactiveSystems } = useMemo(() => {
    const systems = data?.systems ?? []
    const active = systems.filter(isSystemActive)
    const inactive = systems.filter((s) => !isSystemActive(s))
    return { activeSystems: active, inactiveSystems: inactive }
  }, [data?.systems])

  const counts = data?.counts ?? { ok: 0, warning: 0, critical: 0, offline: 0 }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Fleet overview</h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">
            Monitoring {data?.total ?? 0} systems · refreshes every 10 seconds
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          {error ? (
            <span className="text-[var(--color-crit)]">Hub unreachable — is server.py --mode hub running?</span>
          ) : (
            <>
              <span className="flex items-center gap-1.5 text-[var(--color-ok)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-ok)] animate-pulse-dot" />
                Live
              </span>
              {data?.timestamp && (
                <span className="font-mono text-[var(--color-muted)]">
                  Updated {new Date(data.timestamp).toLocaleTimeString()}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryTile label="Healthy" count={counts.ok ?? 0} status="ok" />
        <SummaryTile label="Warning" count={counts.warning ?? 0} status="warning" />
        <SummaryTile label="Critical" count={counts.critical ?? 0} status="critical" />
        <SummaryTile label="Offline" count={counts.offline ?? 0} status="offline" />
      </div>

      {loading && !data ? (
        <p className="text-sm text-[var(--color-muted)]">Loading fleet data…</p>
      ) : null}

      {!loading && data && data.systems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-10 text-center">
          <p className="text-sm text-[var(--color-muted)]">No systems reporting yet.</p>
          <p className="mt-2 font-mono text-xs text-[var(--color-muted)]">
            On each host: python server.py --mode agent --hub http://&lt;hub&gt;:8888 --tag rack=A1
          </p>
        </div>
      ) : null}

      {data && data.systems.length > 0 ? (
        <div className="space-y-8">
          <FleetSection
            title="Active"
            subtitle={`${activeSystems.length} reporting · last seen within ${INACTIVE_AFTER_SEC}s`}
            systems={activeSystems}
            emptyMessage="No systems currently reporting."
          />
          {inactiveSystems.length > 0 ? (
            <FleetSection
              title="Inactive"
              subtitle={`${inactiveSystems.length} not connected · no data for ${INACTIVE_AFTER_SEC}+ seconds`}
              systems={inactiveSystems}
              dimmed
            />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function FleetSection({
  title,
  subtitle,
  systems,
  emptyMessage,
  dimmed,
}: {
  title: string
  subtitle: string
  systems: FleetSystem[]
  emptyMessage?: string
  dimmed?: boolean
}) {
  if (systems.length === 0 && !emptyMessage) return null

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        <p className="mt-0.5 text-[11px] text-[var(--color-muted)]">{subtitle}</p>
      </div>
      {systems.length === 0 ? (
        <p className="text-sm text-[var(--color-muted)]">{emptyMessage}</p>
      ) : (
        <div
          className={`grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 ${dimmed ? 'opacity-80' : ''}`}
        >
          {systems.map((s) => (
            <SystemCard key={s.id} system={s} />
          ))}
        </div>
      )}
    </section>
  )
}

function SummaryTile({
  label,
  count,
  status,
}: {
  label: string
  count: number
  status: 'ok' | 'warning' | 'critical' | 'offline'
}) {
  const c = statusColors(status)
  return (
    <div className={`rounded-xl border bg-[var(--color-surface)] p-4 ${c.border}`}>
      <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      <div className={`mt-1 font-mono text-3xl font-semibold ${c.text}`}>{count}</div>
    </div>
  )
}
