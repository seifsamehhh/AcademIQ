import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, useInView } from "motion/react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, Brain, AlertTriangle,
  Sparkles, Activity, ArrowRight, Flame,
} from "lucide-react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import Footer from "@/components/layout/Footer";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useUser } from "@/context/UserContext";
import { useDashboard } from "@/hooks/api/useDashboard";
import { getPredictedStatus } from "@/data/mockData";
import { cn } from "@/lib/utils";

// ── Animated number counter ────────────────────────────────────────────────────
const useCounter = (target: number, duration = 1200) => {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 4);
      setVal(Math.round(target * ease * 10) / 10);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [inView, target, duration]);

  return { ref, val };
};

// ── Score counter ──────────────────────────────────────────────────────────────
const AnimatedScore = ({ value, className }: { value: number; className?: string }) => {
  const { ref, val } = useCounter(value);
  return (
    <span ref={ref} className={cn("tabular", className)}>
      {val.toFixed(1)}
    </span>
  );
};

// ── Trend icon ─────────────────────────────────────────────────────────────────
const TrendIcon = ({ trend }: { trend: string }) => {
  if (trend === "up")   return <TrendingUp   className="h-3.5 w-3.5 text-emerald-400" />;
  if (trend === "down") return <TrendingDown  className="h-3.5 w-3.5 text-destructive" />;
  return                       <Minus         className="h-3.5 w-3.5 text-muted-foreground" />;
};

// ── Status colour map ──────────────────────────────────────────────────────────
const statusColors: Record<string, { text: string; dot: string; bar: string }> = {
  Excellent: { text: "text-emerald-400", dot: "bg-emerald-400", bar: "[&>div]:bg-emerald-400" },
  Good:      { text: "text-sky-400",     dot: "bg-sky-400",     bar: "[&>div]:bg-sky-400"     },
  Average:   { text: "text-amber-400",   dot: "bg-amber-400",   bar: "[&>div]:bg-amber-400"   },
  "At Risk": { text: "text-destructive", dot: "bg-destructive", bar: "[&>div]:bg-destructive" },
};

// ── Metric card (own component so useCounter is called at hook level) ──────────
interface MetricCardProps {
  label: string;
  value: number;
  suffix: string;
  color: string;
  delay: number;
}

const MetricCard = ({ label, value, suffix, color, delay }: MetricCardProps) => {
  const { ref, val } = useCounter(value);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-xl border border-border/50 bg-card/50 p-4 backdrop-blur-sm
        transition-all hover:border-primary/20 hover:bg-card/80"
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-2 text-3xl font-bold tabular tracking-tight", color)}>
        <span ref={ref}>{suffix === "%" ? val.toFixed(1) : Math.round(val)}</span>
        {suffix && <span className="text-lg font-medium text-muted-foreground">{suffix}</span>}
      </p>
    </motion.div>
  );
};

// ── Fade-in-up wrapper ─────────────────────────────────────────────────────────
const FadeUp = ({
  children, delay = 0, className,
}: { children: React.ReactNode; delay?: number; className?: string }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
    className={className}
  >
    {children}
  </motion.div>
);

// ── Custom chart tooltip ───────────────────────────────────────────────────────
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

// ── Component ──────────────────────────────────────────────────────────────────
const StudentDashboard = () => {
  const { username } = useUser();
  const navigate     = useNavigate();
  const { data, isLoading, isLive } = useDashboard();

  const avgScore    = data.avg_score;
  const weeklyPerf  = data.weekly_performance;
  const engagement  = data.study_engagement;
  const burnoutRisk = data.burnout_risk;
  const predictions = data.course_predictions;
  const stats       = data.quick_stats;

  // Score badge colour
  const scoreColor =
    avgScore >= 85 ? "text-emerald-400" :
    avgScore >= 70 ? "text-sky-400" :
    avgScore >= 55 ? "text-amber-400" : "text-destructive";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Spotlight */}
      <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-60" />

      <DashboardHeader username={username || "Student"} />

      <main className="container relative flex-1 py-8">

        {/* ── Header row ──────────────────────────────────────────────── */}
        <FadeUp className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              Academic Intelligence
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Student Dashboard
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Track your academic performance across all courses.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {isLive && (
              <Badge
                variant="outline"
                className="gap-1.5 border-emerald-500/30 bg-emerald-500/10 text-xs text-emerald-400"
              >
                <motion.span
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                  className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400"
                />
                Live data
              </Badge>
            )}
            <button
              onClick={() => navigate("/student-insights")}
              className="flex items-center gap-1.5 rounded-lg border border-primary/20 bg-primary/5
                px-3 py-1.5 text-xs font-medium text-primary transition-all
                hover:border-primary/40 hover:bg-primary/10"
            >
              <Brain className="h-3.5 w-3.5" />
              AI Insights
              <ArrowRight className="h-3 w-3" />
            </button>
          </div>
        </FadeUp>

        {/* ── Metrics row ─────────────────────────────────────────────── */}
        {isLoading ? (
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MetricCard label="Average Score"    value={avgScore}                suffix="%" color={scoreColor}          delay={0.05} />
            <MetricCard label="Enrolled Courses" value={stats.enrolled_courses}  suffix=""  color="text-foreground"     delay={0.1}  />
            <MetricCard label="Pending Tasks"    value={stats.pending_tasks}     suffix=""  color="text-amber-400"      delay={0.15} />
            <MetricCard label="Upcoming Quizzes" value={stats.upcoming_quizzes}  suffix=""  color="text-primary"        delay={0.2}  />
          </div>
        )}

        {/* ── Performance chart + Burnout ──────────────────────────────── */}
        <div className="mb-6 grid gap-4 lg:grid-cols-3">
          {isLoading ? (
            <>
              <Skeleton className="h-64 rounded-xl lg:col-span-2" />
              <Skeleton className="h-64 rounded-xl" />
            </>
          ) : (
            <>
              {/* Chart */}
              <FadeUp delay={0.2} className="lg:col-span-2">
                <div className="h-64 rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
                  <p className="mb-4 text-sm font-semibold text-foreground">
                    Weekly Performance
                  </p>
                  <ResponsiveContainer width="100%" height="85%">
                    <LineChart data={weeklyPerf} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} domain={[50, 100]} />
                      <Tooltip content={<ChartTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="hsl(var(--primary))"
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: "hsl(var(--primary))", strokeWidth: 0 }}
                        activeDot={{ r: 5, fill: "hsl(var(--primary))", strokeWidth: 2, stroke: "hsl(var(--background))" }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </FadeUp>

              {/* Burnout + Study hours */}
              <FadeUp delay={0.25}>
                <div className="flex h-64 flex-col gap-3 rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
                  <p className="text-sm font-semibold text-foreground">Study Load</p>

                  {/* Burnout alert */}
                  {burnoutRisk && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2"
                    >
                      <Flame className="h-3.5 w-3.5 text-destructive" />
                      <span className="text-xs font-medium text-destructive">Burnout risk detected</span>
                    </motion.div>
                  )}

                  {/* Daily hours bars */}
                  <div className="flex flex-1 flex-col justify-end gap-1.5">
                    {engagement.map((d, i) => {
                      const max = Math.max(...engagement.map(e => e.hours));
                      const pct = max > 0 ? (d.hours / max) * 100 : 0;
                      return (
                        <div key={d.day} className="flex items-center gap-2.5 text-xs">
                          <span className="w-7 text-muted-foreground">{d.day}</span>
                          <div className="flex-1 rounded-full bg-muted/40">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={{ delay: 0.3 + i * 0.04, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                              className={cn(
                                "h-2 rounded-full",
                                burnoutRisk && d.hours === max
                                  ? "bg-destructive"
                                  : "bg-primary/60"
                              )}
                            />
                          </div>
                          <span className="w-8 text-right text-muted-foreground tabular">{d.hours}h</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </FadeUp>
            </>
          )}
        </div>

        {/* ── Course predictions ───────────────────────────────────────── */}
        {isLoading ? (
          <Skeleton className="h-72 w-full rounded-xl" />
        ) : (
          <FadeUp delay={0.3}>
            <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                  <Sparkles className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Predicted Grade per Course</h3>
                  <p className="text-xs text-muted-foreground">AI-projected end-of-term scores</p>
                </div>
              </div>

              <div className="space-y-3">
                {predictions.map((c, i) => {
                  const status = getPredictedStatus(c.score);
                  const s = statusColors[status] ?? statusColors["Average"];
                  return (
                    <motion.div
                      key={c.courseId}
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.35 + i * 0.05, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                      className="grid grid-cols-12 items-center gap-3 rounded-lg px-2 py-2
                        transition-colors hover:bg-muted/30"
                    >
                      <div className="col-span-12 min-w-0 sm:col-span-4">
                        <p className="truncate text-sm font-medium text-foreground">{c.courseName}</p>
                        <div className="mt-0.5 flex items-center gap-1.5 text-xs">
                          <span className={cn("inline-block h-1.5 w-1.5 rounded-full", s.dot)} />
                          <span className={cn("font-medium", s.text)}>{status}</span>
                        </div>
                      </div>
                      <div className="col-span-9 sm:col-span-6">
                        <Progress value={c.score} className={cn("h-1.5 bg-muted/40", s.bar)} />
                      </div>
                      <div className="col-span-3 sm:col-span-2 flex items-center justify-end gap-1.5">
                        <span className="text-sm font-semibold tabular text-foreground">
                          {c.score}
                          <span className="text-xs font-normal text-muted-foreground">/100</span>
                        </span>
                        <TrendIcon trend={c.trend} />
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </FadeUp>
        )}

        {/* ── Engagement summary footer bar ────────────────────────────── */}
        {!isLoading && (
          <FadeUp delay={0.4} className="mt-4">
            <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border/40 bg-muted/20 px-5 py-3 text-xs text-muted-foreground">
              <Activity className="h-3.5 w-3.5 text-primary" />
              <span>
                Weekly avg:{" "}
                <span className="font-semibold text-foreground tabular">
                  {(engagement.reduce((s, d) => s + d.hours, 0) / engagement.length).toFixed(1)}h/day
                </span>
              </span>
              {burnoutRisk ? (
                <span className="flex items-center gap-1 text-destructive">
                  <AlertTriangle className="h-3 w-3" />
                  High variance detected — consider recovery days
                </span>
              ) : (
                <span className="text-emerald-400">Study load looks balanced</span>
              )}
            </div>
          </FadeUp>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default StudentDashboard;
