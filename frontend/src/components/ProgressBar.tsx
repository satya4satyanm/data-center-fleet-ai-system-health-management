import { barColor } from '../lib/status'

export function ProgressBar({ label, pct, className = '' }: { label: string; pct: number; className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <span className="w-[72px] shrink-0 truncate text-[11px] text-[var(--color-muted)] font-mono">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor(pct)}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="w-9 shrink-0 text-right font-mono text-[11px]">{pct}%</span>
    </div>
  )
}
