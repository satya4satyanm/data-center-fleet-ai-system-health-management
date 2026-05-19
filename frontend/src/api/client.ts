import type { FleetSnapshot, SystemRecord } from '../types/metrics'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export function fetchFleet(): Promise<FleetSnapshot> {
  return getJson('/api/fleet')
}

export function fetchSystem(id: string): Promise<SystemRecord> {
  return getJson(`/api/systems/${encodeURIComponent(id)}`)
}
