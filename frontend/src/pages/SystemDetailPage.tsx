import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchSystem } from '../api/client'
import { ProgressBar } from '../components/ProgressBar'
import { StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { fmtGb, fmtRate } from '../lib/format'
import { statusColors } from '../lib/status'
import type { HealthStatus, MetricsPayload } from '../types/metrics'

export function SystemDetailPage() {
  const { id } = useParams<{ id: string }>()
  const load = useCallback(() => fetchSystem(id!), [id])
  const { data, error, loading } = usePolling(load)

  if (!id) return null

  if (loading && !data) {
    return <p className="text-sm text-[var(--color-muted)]">Loading system…</p>
  }

  if (error || !data) {
    return (
      <div>
        <BackLink />
        <p className="mt-4 text-[var(--color-crit)]">{error ?? 'System not found'}</p>
      </div>
    )
  }

  const m = data.metrics
  const sys = m.system

  return (
    <div>
      <BackLink />
      <div className="mb-6 mt-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-mono text-xl font-semibold text-white">{sys.hostname}</h1>
          <p className="text-sm text-[var(--color-muted)]">
            {sys.os} {sys.os_release} · {sys.machine} · uptime {sys.uptime_str}
          </p>
        </div>
        <StatusBadge status={data.status} />
      </div>

      <AlertsBanner metrics={m} />

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="CPU" value={`${m.cpu.avg_pct}%`} status={m.cpu.status} sub={`load ${m.cpu.load_avg_1m}`} />
        <StatCard label="RAM" value={`${m.memory.pct}%`} status={m.memory.status} sub={fmtGb(m.memory.used_mb) + ' used'} />
        <StatCard
          label="Disks"
          value={`${worstDiskPct(m)}%`}
          status={worstDiskStatus(m)}
          sub={`${m.disks.length} volume(s)`}
        />
        <StatCard
          label="GPU"
          value={m.gpu[0] ? `${m.gpu[0].temp_c}°C` : 'N/A'}
          status={m.gpu[0]?.status ?? 'ok'}
          sub={m.gpu[0]?.name ?? 'no GPU'}
        />
      </div>

      <Section title="CPU">
        <Card title="Processor" status={m.cpu.status}>
          {m.cpu.cores.slice(0, 12).map((c) => (
            <ProgressBar key={c.id} label={`Core ${c.id}`} pct={c.pct} className="mb-2" />
          ))}
          <KvTable
            rows={[
              ['Load 1m / 5m / 15m', `${m.cpu.load_avg_1m} / ${m.cpu.load_avg_5m} / ${m.cpu.load_avg_15m}`],
              ['Frequency', m.cpu.freq_mhz ? `${m.cpu.freq_mhz} MHz` : '—'],
              ['Threads', String(m.cpu.count_logical ?? '—')],
            ]}
          />
        </Card>
      </Section>

      <Section title="Memory & storage">
        <div className="grid gap-3 lg:grid-cols-2">
          <Card title="Memory" status={m.memory.status}>
            <ProgressBar label="RAM" pct={m.memory.pct} className="mb-2" />
            <ProgressBar label="Swap" pct={m.memory.swap_pct} className="mb-3" />
            <KvTable
              rows={[
                ['Total', fmtGb(m.memory.total_mb)],
                ['Used', fmtGb(m.memory.used_mb)],
                ['Available', fmtGb(m.memory.available_mb)],
              ]}
            />
          </Card>
          <Card title="Disks" status={worstDiskStatus(m)}>
            {m.disks.length === 0 ? (
              <p className="text-sm italic text-[var(--color-muted)]">No disks</p>
            ) : (
              m.disks.map((d) => (
                <div key={d.device} className="mb-4 last:mb-0">
                  <ProgressBar label={d.device.replace('/dev/', '')} pct={d.pct} className="mb-1" />
                  <p className="mb-2 font-mono text-[10px] text-[var(--color-muted)]">
                    {d.used_gb}/{d.total_gb} GB · {d.mountpoint}
                  </p>
                </div>
              ))
            )}
          </Card>
        </div>
        {(m.memory.top_apps?.length ?? 0) > 0 && (
          <Card title="Top memory consumers" status="ok" className="mt-3">
            {m.memory.top_apps!.map((a) => (
              <ProgressBar key={a.name} label={a.name.slice(0, 18)} pct={a.mem_pct} className="mb-2" />
            ))}
          </Card>
        )}
      </Section>

      <Section title="GPU & thermals">
        <div className="grid gap-3 lg:grid-cols-2">
          <Card title="GPU" status={m.gpu[0]?.status ?? 'ok'}>
            {m.gpu.length === 0 ? (
              <p className="text-sm italic text-[var(--color-muted)]">No GPU detected</p>
            ) : (
              m.gpu.map((g) => (
                <div key={g.name} className="mb-3 last:mb-0">
                  <p className="mb-2 font-mono text-[11px] text-[var(--color-muted)]">{g.name}</p>
                  {g.load_pct != null && <ProgressBar label="Load" pct={g.load_pct} className="mb-2" />}
                  <KvTable rows={[['Temperature', `${g.temp_c}°C`]]} />
                </div>
              ))
            )}
          </Card>
          <Card title="Thermals" status={worstThermalStatus(m)}>
            {m.thermals.length === 0 ? (
              <p className="text-sm italic text-[var(--color-muted)]">No sensors</p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {m.thermals.slice(0, 8).map((t) => (
                  <div key={t.name} className="rounded-lg bg-[var(--color-surface-2)] p-2.5">
                    <p className="text-[10px] text-[var(--color-muted)]">{t.name}</p>
                    <p className={`font-mono text-base font-semibold ${statusColors(t.status).text}`}>
                      {t.temp_c}°C
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </Section>

      <Section title="Network">
        <Card title="Interfaces" status={worstNetStatus(m)}>
          {m.network.filter((n) => n.name !== 'lo').map((n) => (
            <div key={n.name} className="mb-4 border-b border-[var(--color-border)] pb-4 last:mb-0 last:border-0 last:pb-0">
              <p className="mb-2 font-mono text-xs font-semibold text-[var(--color-muted)]">{n.name}</p>
              <KvTable
                rows={[
                  ['Download', fmtRate(n.rx_rate_kbps)],
                  ['Upload', fmtRate(n.tx_rate_kbps)],
                  ['Drops', String(n.drops_in + n.drops_out)],
                  ['Errors', String(n.errors_in + n.errors_out)],
                ]}
              />
            </div>
          ))}
        </Card>
      </Section>

      <Section title="Logs">
        <Card title="Recent warnings" status="ok">
          {m.logs.length === 0 ? (
            <p className="text-sm text-[var(--color-ok)]">No warnings in the last 2 hours.</p>
          ) : (
            <ul className="max-h-52 space-y-2 overflow-y-auto font-mono text-[10px]">
              {m.logs.map((l, i) => (
                <li key={i} className="text-[var(--color-muted)]">
                  <span className="text-[var(--color-muted)]">{l.time?.slice(11, 16) || '--:--'}</span>{' '}
                  {l.unit ? `[${l.unit}] ` : ''}
                  {l.msg}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </Section>
    </div>
  )
}

function BackLink() {
  return (
    <Link to="/" className="text-[11px] text-[var(--color-muted)] hover:text-white">
      ← Fleet overview
    </Link>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-5">
      <h2 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-muted)]">
        {title}
      </h2>
      {children}
    </section>
  )
}

function Card({
  title,
  status,
  children,
  className = '',
}: {
  title: string
  status: HealthStatus
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 ${className}`}>
      <div className="mb-3 flex items-center justify-between border-b border-[var(--color-border)] pb-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">{title}</span>
        <StatusBadge status={status} />
      </div>
      {children}
    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
  status,
}: {
  label: string
  value: string
  sub: string
  status: HealthStatus
}) {
  const c = statusColors(status)
  return (
    <div className={`rounded-xl border bg-[var(--color-surface)] p-4 ${c.border}`}>
      <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      <div className={`mt-1 font-mono text-2xl font-semibold ${c.text}`}>{value}</div>
      <div className="mt-1 text-[10px] text-[var(--color-muted)]">{sub}</div>
    </div>
  )
}

function KvTable({ rows }: { rows: [string, string][] }) {
  return (
    <table className="w-full text-[11px]">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td className="py-0.5 text-[var(--color-muted)]">{k}</td>
            <td className="py-0.5 text-right font-mono text-white">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function worstDiskPct(m: MetricsPayload) {
  if (!m.disks.length) return 0
  return Math.max(...m.disks.map((d) => d.pct))
}

function worstDiskStatus(m: MetricsPayload): HealthStatus {
  if (m.disks.some((d) => d.status === 'critical')) return 'critical'
  if (m.disks.some((d) => d.status === 'warning')) return 'warning'
  return 'ok'
}

function worstThermalStatus(m: MetricsPayload): HealthStatus {
  if (m.thermals.some((t) => t.status === 'critical')) return 'critical'
  if (m.thermals.some((t) => t.status === 'warning')) return 'warning'
  return 'ok'
}

function worstNetStatus(m: MetricsPayload): HealthStatus {
  const nets = m.network.filter((n) => n.name !== 'lo')
  if (nets.some((n) => n.status === 'warning')) return 'warning'
  return 'ok'
}

function AlertsBanner({ metrics }: { metrics: MetricsPayload }) {
  const warnings: string[] = []
  const crits: string[] = []
  if (metrics.cpu.status === 'critical') crits.push(`CPU ${metrics.cpu.avg_pct}%`)
  else if (metrics.cpu.status === 'warning') warnings.push(`CPU ${metrics.cpu.avg_pct}%`)
  if (metrics.memory.status === 'critical') crits.push(`RAM ${metrics.memory.pct}%`)
  else if (metrics.memory.status === 'warning') warnings.push(`RAM ${metrics.memory.pct}%`)
  for (const g of metrics.gpu) {
    if (g.status === 'critical') crits.push(`GPU ${g.temp_c}°C`)
    else if (g.status === 'warning') warnings.push(`GPU ${g.temp_c}°C`)
  }
  if (!crits.length && !warnings.length) return null
  const critical = crits.length > 0
  return (
    <div
      className={`mb-4 rounded-lg border px-4 py-2 font-mono text-xs ${
        critical
          ? 'border-[var(--color-crit)]/30 bg-[var(--color-crit)]/10 text-[var(--color-crit)]'
          : 'border-[var(--color-warn)]/30 bg-[var(--color-warn)]/10 text-[var(--color-warn)]'
      }`}
    >
      {critical ? 'CRITICAL: ' : ''}
      {[...crits, ...warnings].join(' · ')}
    </div>
  )
}
