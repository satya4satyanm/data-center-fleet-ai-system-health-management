export type HealthStatus = 'ok' | 'warning' | 'critical' | 'offline'

export interface FleetSystem {
  id: string
  hostname: string
  os?: string
  os_release?: string
  machine?: string
  uptime_str?: string
  tags: Record<string, string>
  status: HealthStatus
  online: boolean
  last_seen?: string
  last_seen_ago_sec?: number
  timestamp?: string
  cpu_pct?: number
  memory_pct?: number
  load_avg_1m?: number
  alert_count?: number
}

export interface FleetSnapshot {
  timestamp: string
  total: number
  counts: Record<string, number>
  systems: FleetSystem[]
}

export interface SystemRecord {
  id: string
  status: HealthStatus
  tags: Record<string, string>
  last_seen: string
  metrics: MetricsPayload
}

export interface MetricsPayload {
  timestamp: string
  system: {
    hostname: string
    os: string
    os_version?: string
    os_release?: string
    machine?: string
    uptime_str?: string
    uptime_seconds?: number
  }
  cpu: {
    avg_pct: number
    cores: { id: number; pct: number }[]
    load_avg_1m: number
    load_avg_5m: number
    load_avg_15m: number
    freq_mhz?: number
    count_logical?: number
    status: HealthStatus
  }
  memory: {
    pct: number
    used_mb: number
    total_mb: number
    available_mb: number
    swap_pct: number
    status: HealthStatus
    top_apps?: { name: string; mem_mb: number; mem_pct: number; processes: number }[]
  }
  disks: {
    device: string
    mountpoint: string
    pct: number
    used_gb: number
    total_gb: number
    status: HealthStatus
    smart?: Record<string, number | string | null>
  }[]
  gpu: {
    name: string
    temp_c: number
    load_pct?: number
    mem_pct?: number
    status: HealthStatus
  }[]
  thermals: { name: string; temp_c: number; status: HealthStatus }[]
  network: {
    name: string
    rx_rate_kbps: number
    tx_rate_kbps: number
    drops_in: number
    drops_out: number
    errors_in: number
    errors_out: number
    status: HealthStatus
  }[]
  battery: {
    present: boolean
    pct?: number
    status?: string
    health_pct?: number
  }
  logs: { time: string; unit?: string; msg: string }[]
}
