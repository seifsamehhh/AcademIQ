import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { PerformanceData } from "@/data/mockData";

interface PerformanceChartProps {
  data: PerformanceData[];
  title: string;
}

const ChartTooltip = ({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-card/95 px-3 py-2 text-xs backdrop-blur-sm">
      <p className="mb-1 font-medium text-muted-foreground">{label}</p>
      <p className="font-semibold text-foreground tabular">{payload[0].value}%</p>
    </div>
  );
};

const PerformanceChart = ({ data, title }: PerformanceChartProps) => {
  return (
    <div>
      {title && (
        <p className="mb-4 text-sm font-semibold text-foreground">{title}</p>
      )}
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(var(--border))"
              strokeOpacity={0.5}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="score"
              stroke="hsl(var(--primary))"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "hsl(var(--primary))", strokeWidth: 0 }}
              activeDot={{
                r: 5,
                fill: "hsl(var(--primary))",
                strokeWidth: 2,
                stroke: "hsl(var(--background))",
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default PerformanceChart;
