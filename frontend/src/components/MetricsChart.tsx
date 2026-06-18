import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface DataPoint {
  time: string;
  processed: number;
  failed: number;
}

interface Props {
  data: DataPoint[];
}

export default function MetricsChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-gray-600">
        Sin datos de timeline disponibles
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="colorProcessed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 10, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#111827",
            border: "1px solid #374151",
            borderRadius: "6px",
            fontSize: "11px",
          }}
          labelStyle={{ color: "#9ca3af" }}
        />
        <Area
          type="monotone"
          dataKey="processed"
          name="Procesadas"
          stroke="#22c55e"
          strokeWidth={2}
          fill="url(#colorProcessed)"
        />
        <Area
          type="monotone"
          dataKey="failed"
          name="Fallidas"
          stroke="#ef4444"
          strokeWidth={2}
          fill="url(#colorFailed)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
