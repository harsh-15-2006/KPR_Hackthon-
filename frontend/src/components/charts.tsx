import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SourceBreakdown, SourceKey } from '../types'
import { SOURCE_COLORS, formatCo2e } from '../utils/format'

const tooltipStyle = {
  borderRadius: 8,
  border: '1px solid #e4e7ec',
  fontSize: 12,
  boxShadow: '0 4px 12px rgba(16,24,40,0.08)',
}

/** Donut: share of total CO2e per source. */
export function SourceDonut({ data }: { data: SourceBreakdown[] }) {
  const rows = data.filter((d) => d.co2e > 0)
  if (rows.length === 0) {
    return <p className="p-8 text-center text-sm text-[#667085]">No emissions recorded yet.</p>
  }
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={rows}
          dataKey="co2e"
          nameKey="label"
          innerRadius={65}
          outerRadius={100}
          paddingAngle={2}
        >
          {rows.map((r) => (
            <Cell key={r.source} fill={SOURCE_COLORS[r.source as SourceKey]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value, _name, item) => {
            const row = (item as { payload?: SourceBreakdown })?.payload
            const n = Number(value) || 0
            return [
              `${formatCo2e(n)} (${row?.contribution_pct ?? 0}%)`,
              row?.label ?? 'CO2e',
            ]
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={28}
          iconType="circle"
          formatter={(v) => <span style={{ fontSize: 12, color: '#475467' }}>{v}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

/** Bar: absolute CO2e per source. */
export function SourceBar({ data }: { data: SourceBreakdown[] }) {
  if (data.every((d) => d.co2e === 0)) {
    return <p className="p-8 text-center text-sm text-[#667085]">No emissions recorded yet.</p>
  }
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e3e8e6" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: '#667085' }}
          axisLine={{ stroke: '#e4e7ec' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#667085' }}
          axisLine={false}
          tickLine={false}
          width={70}
          tickFormatter={(v: number) => formatCo2e(v)}
        />
        <Tooltip
          cursor={{ fill: '#f9fafb' }}
          contentStyle={tooltipStyle}
          formatter={(value) => [formatCo2e(Number(value) || 0), 'CO2e']}
        />
        <Bar dataKey="co2e" radius={[6, 6, 0, 0]} maxBarSize={64}>
          {data.map((r) => (
            <Cell key={r.source} fill={SOURCE_COLORS[r.source as SourceKey]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
