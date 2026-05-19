import type { HealthStatus } from '../types/metrics'

export function statusLabel(s: HealthStatus): string {
  switch (s) {
    case 'critical':
      return 'Critical'
    case 'warning':
      return 'Warning'
    case 'offline':
      return 'Offline'
    default:
      return 'Healthy'
  }
}

export function statusColors(s: HealthStatus) {
  switch (s) {
    case 'critical':
      return {
        text: 'text-[var(--color-crit)]',
        bg: 'bg-[var(--color-crit)]/10',
        border: 'border-[var(--color-crit)]/30',
        bar: 'bg-[var(--color-crit)]',
        dot: 'bg-[var(--color-crit)]',
      }
    case 'warning':
      return {
        text: 'text-[var(--color-warn)]',
        bg: 'bg-[var(--color-warn)]/10',
        border: 'border-[var(--color-warn)]/30',
        bar: 'bg-[var(--color-warn)]',
        dot: 'bg-[var(--color-warn)]',
      }
    case 'offline':
      return {
        text: 'text-[var(--color-offline)]',
        bg: 'bg-white/5',
        border: 'border-white/10',
        bar: 'bg-[var(--color-offline)]',
        dot: 'bg-[var(--color-offline)]',
      }
    default:
      return {
        text: 'text-[var(--color-ok)]',
        bg: 'bg-[var(--color-ok)]/10',
        border: 'border-[var(--color-ok)]/30',
        bar: 'bg-[var(--color-ok)]',
        dot: 'bg-[var(--color-ok)]',
      }
  }
}

export function barColor(pct: number): string {
  if (pct >= 90) return 'bg-[var(--color-crit)]'
  if (pct >= 70) return 'bg-[var(--color-warn)]'
  return 'bg-[var(--color-ok)]'
}
