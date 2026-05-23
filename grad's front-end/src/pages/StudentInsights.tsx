import { useNavigate } from "react-router-dom";
import { motion, useInView } from "motion/react";
import { useRef, useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  Trophy, AlertTriangle, TrendingUp, TrendingDown,
  CheckCircle2, Sparkles, BookOpen, Clock, Activity,
  Target, Brain, ArrowLeft, Calendar,
} from "lucide-react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import Footer from "@/components/layout/Footer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useUser } from "@/context/UserContext";
import { useInsights } from "@/hooks/api/useInsights";
import { cn } from "@/lib/utils";

type Classification = "High Performer" | "Average Performer" | "At Risk";

// ── Config ──────────────────────────────────────────────────────────────────────
const classificationConfig: Record<
  Classification,
  { icon: typeof Trophy; color: string; bg: string; border: string; glow: string; explanation: string }
> = {
  "High Performer": {
    icon:        Trophy,
    color:       "text-emerald-400",
    bg:          "bg-emerald-500/8",
    border:      "border-emerald-500/25",
    glow:        "shadow-[0_0_30px_hsl(160_84%_39%_/_0.15)]",
    explanation: "Engagement and assessment patterns classify this student as a High Performer.",
  },
  "Average Performer": {
    icon:        Activity,
    color:       "text-amber-400",
    bg:          "bg-amber-500/8",
    border:      "border-amber-500/25",
    glow:        "shadow-[0_0_30px_hsl(38_92%_50%_/_0.12)]",
    explanation: "Steady engagement with clear room to grow toward top-tier performance.",
  },
  "At Risk": {
    icon:        AlertTriangle,
    color:       "text-destructive",
    bg:          "bg-destructive/8",
    border:      "border-destructive/25",
    glow:        "shadow-[0_0_30px_hsl(0_72%_55%_/_0.15)]",
    explanation: "Engagement and assessment patterns suggest this student needs immediate support.",
  },
};

// ── Animated confidence bar ────────────────────────────────────────────────────
const AnimatedProgress = ({ value, className }: { value: number; className?: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const timer = setTimeout(() => setProgress(value), 200);
    return () => clearTimeout(timer);
  }, [inView, value]);

  return (
    <div ref={ref}>
      <Progress
        value={progress}
        className={cn("transition-all duration-1000 ease-out", className)}
      />
    </div>
  );
};

// ── Fade-up wrapper ────────────────────────────────────────────────────────────
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

// ── Tone helpers ───────────────────────────────────────────────────────────────
const toneStyle = (tone: string) =>
  tone === "success" ? "bg-emerald-400" :
  tone === "warning" ? "bg-amber-400" : "bg-primary";

const ToneIcon = ({ tone }: { tone: string }) =>
  tone === "success" ? <TrendingUp  className="h-3.5 w-3.5 text-emerald-400" /> :
  tone === "warning" ? <TrendingDown className="h-3.5 w-3.5 text-amber-400" /> :
                       <Sparkles    className="h-3.5 w-3.5 text-primary" />;

const priorityVariant = (p: string) =>
  p === "High"   ? "border-destructive/30 bg-destructive/10 text-destructive" :
  p === "Medium" ? "border-amber-500/30 bg-amber-500/10 text-amber-400" :
                   "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";

// ── Custom chart tooltip ───────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }: {
  active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-card/95 px-3 py-2.5 text-xs backdrop-blur-sm">
      <p className="mb-2 font-medium text-muted-foreground">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-semibold text-foreground tabular">{p.value}</span>
        </div>
      ))}
    </div>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────
const StudentInsights = () => {
  const { username } = useUser();
  const navigate     = useNavigate();
  const { data, isLoading, isLive } = useInsights();

  const classification = data.classification as Classification;
  const confidence     = data.confidence;
  const cfg            = classificationConfig[classification];
  const ClassIcon      = cfg.icon;

  const recIcons = [BookOpen, Clock, Sparkles, Activity, CheckCircle2];
  const strengthIcons = [CheckCircle2, TrendingUp, Target, CheckCircle2, Activity];
  const weaknessIcons = [Clock, Activity, BookOpen, AlertTriangle, Clock];

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Spotlight */}
      <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-60" />

      <DashboardHeader username={username || "Student"} />

      <main className="container relative flex-1 py-8">

        {/* ── Header row ──────────────────────────────────────────────── */}
        <FadeUp className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(-1)}
              className="mb-2 h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              ML Analysis
            </p>
            <h1 className="flex items-center gap-2.5 text-3xl font-bold tracking-tight text-foreground">
              <Brain className="h-7 w-7 text-primary" />
              Student Insights
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              AI-generated analysis of your performance and study behavior.
            </p>
          </div>

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
              Live ML data
            </Badge>
          )}
        </FadeUp>

        {/* ── Classification card ──────────────────────────────────────── */}
        {isLoading ? (
          <Skeleton className="mb-6 h-36 w-full rounded-xl" />
        ) : (
          <FadeUp delay={0.1} className="mb-6">
            <motion.div
              whileHover={{ scale: 1.005 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className={cn(
                "rounded-xl border p-6 backdrop-blur-sm transition-all",
                cfg.border, cfg.bg, cfg.glow,
              )}
            >
              <div className="flex flex-col gap-6 md:flex-row md:items-center">
                {/* Icon */}
                <motion.div
                  initial={{ scale: 0, rotate: -10 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200, damping: 20 }}
                  className={cn(
                    "flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl",
                    cfg.bg,
                  )}
                >
                  <ClassIcon className={cn("h-8 w-8", cfg.color)} />
                </motion.div>

                {/* Label */}
                <div className="flex-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                    Student Classification
                  </p>
                  <h2 className={cn("mt-1 text-2xl font-bold", cfg.color)}>
                    {classification}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm text-muted-foreground leading-relaxed">
                    {cfg.explanation}
                  </p>
                </div>

                {/* Confidence */}
                <div className="w-full md:w-52">
                  <div className="mb-2 flex justify-between text-xs text-muted-foreground">
                    <span>AI Confidence</span>
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.6 }}
                      className={cn("font-bold tabular", cfg.color)}
                    >
                      {confidence}%
                    </motion.span>
                  </div>
                  <AnimatedProgress
                    value={confidence}
                    className={cn(
                      "h-2 bg-muted/40",
                      classification === "High Performer" ? "[&>div]:bg-emerald-400" :
                      classification === "Average Performer" ? "[&>div]:bg-amber-400" :
                      "[&>div]:bg-destructive"
                    )}
                  />
                </div>
              </div>
            </motion.div>
          </FadeUp>
        )}

        {/* ── Strengths + Recommendations ─────────────────────────────── */}
        <div className="mb-6 grid gap-4 lg:grid-cols-2">
          {isLoading ? (
            <>
              <Skeleton className="h-72 rounded-xl" />
              <Skeleton className="h-72 rounded-xl" />
            </>
          ) : (
            <>
              {/* Strengths + Weaknesses */}
              <FadeUp delay={0.2}>
                <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold text-foreground">Behavioral Analysis</h3>
                  </div>

                  <div className="space-y-5">
                    {/* Strengths */}
                    <div>
                      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-emerald-400">
                        Strengths
                      </p>
                      <ul className="space-y-2">
                        {data.strengths.map((s, i) => {
                          const Icon = strengthIcons[i] ?? CheckCircle2;
                          return (
                            <motion.li
                              key={i}
                              initial={{ opacity: 0, x: -12 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: 0.3 + i * 0.07, duration: 0.4 }}
                              className="flex items-start gap-2.5 rounded-lg border border-emerald-500/15
                                bg-emerald-500/5 px-3 py-2.5"
                            >
                              <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                              <span className="text-sm text-foreground/90">{s}</span>
                            </motion.li>
                          );
                        })}
                      </ul>
                    </div>

                    {/* Weaknesses */}
                    <div>
                      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-destructive">
                        Areas to Improve
                      </p>
                      <ul className="space-y-2">
                        {data.weaknesses.map((w, i) => {
                          const Icon = weaknessIcons[i] ?? Activity;
                          return (
                            <motion.li
                              key={i}
                              initial={{ opacity: 0, x: -12 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: 0.45 + i * 0.07, duration: 0.4 }}
                              className="flex items-start gap-2.5 rounded-lg border border-destructive/15
                                bg-destructive/5 px-3 py-2.5"
                            >
                              <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
                              <span className="text-sm text-foreground/90">{w}</span>
                            </motion.li>
                          );
                        })}
                      </ul>
                    </div>
                  </div>
                </div>
              </FadeUp>

              {/* Recommendations */}
              <FadeUp delay={0.25}>
                <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold text-foreground">AI Recommendations</h3>
                  </div>
                  <div className="space-y-2.5">
                    {data.recommendations.map((r, i) => {
                      const Icon = recIcons[i] ?? BookOpen;
                      return (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.3 + i * 0.06, duration: 0.4 }}
                          className="group flex items-start gap-3 rounded-xl border border-border/40
                            bg-muted/20 p-3 transition-all hover:border-primary/25 hover:bg-primary/5"
                        >
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg
                            bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
                            <Icon className="h-3.5 w-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-foreground truncate">{r.title}</p>
                              <Badge
                                variant="outline"
                                className={cn("shrink-0 text-[10px]", priorityVariant(r.priority))}
                              >
                                {r.priority}
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                              {r.description}
                            </p>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                </div>
              </FadeUp>
            </>
          )}
        </div>

        {/* ── Progress chart ───────────────────────────────────────────── */}
        {isLoading ? (
          <Skeleton className="mb-6 h-72 w-full rounded-xl" />
        ) : (
          <FadeUp delay={0.3} className="mb-6">
            <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
              <div className="mb-4 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold text-foreground">Progress Tracking</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.progress_data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} />
                    <XAxis dataKey="week" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Legend wrapperStyle={{ fontSize: "11px", color: "hsl(var(--muted-foreground))" }} />
                    <Line type="monotone" dataKey="engagement" name="Engagement"            stroke="hsl(var(--primary))"  strokeWidth={2} dot={{ r: 2.5 }} activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="quiz"       name="Quiz Scores"           stroke="hsl(160 84% 39%)"     strokeWidth={2} dot={{ r: 2.5 }} />
                    <Line type="monotone" dataKey="predicted"  name="Predicted"             stroke="hsl(38 92% 50%)"      strokeWidth={2} strokeDasharray="5 5" dot={{ r: 2.5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </FadeUp>
        )}

        {/* ── Timeline ────────────────────────────────────────────────── */}
        {isLoading ? (
          <Skeleton className="h-56 w-full rounded-xl" />
        ) : (
          <FadeUp delay={0.35}>
            <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
              <div className="mb-5 flex items-center gap-2">
                <Calendar className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold text-foreground">Recommendation Timeline</h3>
              </div>
              <div className="relative pl-5">
                <div className="absolute bottom-0 left-1.5 top-0 w-px bg-gradient-to-b from-border via-border/50 to-transparent" />
                <ul className="space-y-4">
                  {data.timeline.map((t, i) => (
                    <motion.li
                      key={i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.4 + i * 0.07, duration: 0.4 }}
                      className="relative"
                    >
                      <span
                        className={cn(
                          "absolute -left-[18px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-background",
                          toneStyle(t.tone),
                        )}
                      />
                      <div className="rounded-lg border border-border/40 bg-muted/20 px-4 py-3
                        transition-all hover:border-primary/20 hover:bg-primary/5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                            {t.week}
                          </span>
                          <ToneIcon tone={t.tone} />
                        </div>
                        <p className="mt-1.5 text-sm text-foreground/90">{t.text}</p>
                      </div>
                    </motion.li>
                  ))}
                </ul>
              </div>
            </div>
          </FadeUp>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default StudentInsights;
