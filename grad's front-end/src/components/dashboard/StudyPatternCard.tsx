import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "@/lib/utils";

export interface EngagementPoint {
  day: string;
  hours: number;
}

interface StudyPatternCardProps {
  data: EngagementPoint[];
  burnoutRisk?: boolean;
}

const StudyPatternCard = ({ data, burnoutRisk = false }: StudyPatternCardProps) => {
  const status = burnoutRisk ? "Burnout Risk" : "Healthy Pattern";
  const insight = burnoutRisk
    ? "Sudden spike in activity detected — possible burnout risk."
    : "Consistent healthy engagement detected across the week.";
  const Icon = burnoutRisk ? AlertTriangle : CheckCircle2;
  const accent = burnoutRisk ? "text-amber-600" : "text-emerald-600";
  const accentBg = burnoutRisk ? "bg-amber-500/10 border-amber-500/30" : "bg-emerald-500/10 border-emerald-500/30";
  const lineColor = burnoutRisk ? "hsl(38 92% 50%)" : "hsl(160 60% 40%)";

  return (
    <div className="group rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Activity className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">Study Pattern Analysis</p>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 mt-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              accentBg,
              accent
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {status}
          </span>
        </div>
      </div>

      <div className="h-24 w-full -mx-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 8, left: 8, bottom: 0 }}>
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                borderColor: "hsl(var(--border))",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              labelStyle={{ color: "hsl(var(--card-foreground))" }}
            />
            <Line
              type="monotone"
              dataKey="hours"
              stroke={lineColor}
              strokeWidth={2.5}
              dot={{ r: 3, fill: lineColor }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-3 text-sm text-muted-foreground">{insight}</p>
    </div>
  );
};

export default StudyPatternCard;