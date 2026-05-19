export function fmtGb(mb: number): string {
  const gb = mb / 1024
  return (gb >= 10 ? Math.round(gb) : Math.round(gb * 10) / 10) + ' GB'
}

export function fmtMem(mb: number): string {
  return mb >= 1024 ? fmtGb(mb) : Math.round(mb) + ' MB'
}

export function fmtRate(kbps: number): string {
  if (kbps >= 1024) return (kbps / 1024).toFixed(1) + ' MB/s'
  return kbps.toFixed(1) + ' KB/s'
}

export function timeAgo(sec?: number): string {
  if (sec == null) return '—'
  if (sec < 60) return `${Math.round(sec)}s ago`
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`
  return `${Math.round(sec / 3600)}h ago`
}
