import type { SourceKey } from '../types'

/** kg CO2e -> compact human string. */
export function formatCo2e(kg: number): string {
  if (!Number.isFinite(kg)) return '0'
  if (Math.abs(kg) >= 1_000_000) return `${(kg / 1_000_000).toFixed(2)} kt`
  if (Math.abs(kg) >= 1_000) return `${(kg / 1_000).toFixed(2)} t`
  return `${kg.toFixed(2)} kg`
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-IN').format(n)
}

export const SOURCE_LABELS: Record<SourceKey, string> = {
  electricity: 'Electricity',
  fuel: 'Fuel',
  logistics: 'Logistics',
  production: 'Production',
  waste: 'Waste',
}

/** One consistent colour per source, used by every chart and badge. */
export const SOURCE_COLORS: Record<SourceKey, string> = {
  electricity: '#2563eb',
  fuel: '#ea580c',
  logistics: '#0d9488',
  production: '#7c3aed',
  waste: '#65a30d',
}

export const ALL_SOURCES: SourceKey[] = [
  'electricity',
  'fuel',
  'logistics',
  'production',
  'waste',
]
