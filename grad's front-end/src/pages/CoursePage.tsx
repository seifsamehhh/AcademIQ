import { useState, useMemo } from "react";
import { useParams, Navigate, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import { useUser } from "@/context/UserContext";
import Footer from "@/components/layout/Footer";
import PerformanceChart from "@/components/dashboard/PerformanceChart";
import StatusBadge from "@/components/dashboard/StatusBadge";
import CourseStatistics from "@/components/dashboard/CourseStatistics";
import ChapterSelect from "@/components/dashboard/ChapterSelect";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sparkles, FileText, Brain, BookOpen, ArrowRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  courses,
  coursePerformanceData,
  courseStats,
  getCourseStatus,
} from "@/data/mockData";

// ── Fade-up wrapper ────────────────────────────────────────────────────────────
const FadeUp = ({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    className={className}
  >
    {children}
  </motion.div>
);

// ── Component ──────────────────────────────────────────────────────────────────
const CoursePage = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const { username } = useUser();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState("all");
  const [selectedChapters, setSelectedChapters] = useState<string[]>([]);

  const course = courses.find((c) => c.id === courseId);
  const performanceData = courseId ? coursePerformanceData[courseId] ?? [] : [];
  const stats = courseId ? courseStats[courseId] : undefined;

  const filteredData = useMemo(() => {
    switch (dateRange) {
      case "week":   return performanceData.slice(-1);
      case "2weeks": return performanceData.slice(-2);
      case "month":  return performanceData.slice(-4);
      default:       return performanceData;
    }
  }, [performanceData, dateRange]);

  const avgScore = filteredData.length
    ? filteredData.reduce((s, d) => s + d.score, 0) / filteredData.length
    : 0;
  const courseStatus = getCourseStatus(avgScore);

  if (!course || !courseId) return <Navigate to="/dashboard" replace />;

  const handleGenerateQuiz = () => {
    if (!selectedChapters.length) {
      toast({ title: "No chapters selected", description: "Select at least one chapter.", variant: "destructive" });
      return;
    }
    navigate("/generated-quizzes", { state: { courseId, chapters: selectedChapters } });
  };

  const handleGenerateNotes = () => {
    if (!selectedChapters.length) {
      toast({ title: "No chapters selected", description: "Select at least one chapter.", variant: "destructive" });
      return;
    }
    navigate("/generated-notes", { state: { courseId, chapters: selectedChapters } });
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Spotlight */}
      <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-50" />

      <DashboardHeader username={username || "Student"} />

      <main className="container relative flex-1 py-8">

        {/* ── Page header ────────────────────────────────────────────── */}
        <FadeUp className="mb-8">
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Course Detail
          </p>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                <BookOpen className="h-3.5 w-3.5" />
                <span>{course.code}</span>
                <span className="opacity-40">·</span>
                <span>{course.instructor}</span>
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">
                {course.name}
              </h1>
            </div>

            <button
              onClick={() => navigate("/student-insights", { state: { courseId } })}
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

        {/* ── Performance chart + status ──────────────────────────────── */}
        <div className="mb-6 grid gap-4 lg:grid-cols-3">
          {/* Chart card */}
          <FadeUp delay={0.08} className="lg:col-span-2">
            <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-semibold text-foreground">Course Performance</p>
                <Select value={dateRange} onValueChange={setDateRange}>
                  <SelectTrigger className="h-8 w-[160px] border-border/60 bg-card/50 text-xs backdrop-blur-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-border/60 bg-card/95 backdrop-blur-xl text-xs">
                    <SelectItem value="week">Last week</SelectItem>
                    <SelectItem value="2weeks">Last 2 weeks</SelectItem>
                    <SelectItem value="month">Last month</SelectItem>
                    <SelectItem value="all">All time</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <PerformanceChart data={filteredData} title="" />
            </div>
          </FadeUp>

          {/* Status + avg score */}
          <FadeUp delay={0.12} className="flex flex-col gap-4">
            <StatusBadge status={courseStatus} type="course" />

            <div className="flex-1 rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
              <p className="mb-3 text-xs text-muted-foreground">Course average</p>
              <p className="text-4xl font-bold tabular tracking-tight text-primary">
                {avgScore.toFixed(1)}
                <span className="text-xl font-medium text-muted-foreground">%</span>
              </p>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Based on {filteredData.length} data point{filteredData.length !== 1 ? "s" : ""}
              </p>
            </div>
          </FadeUp>
        </div>

        {/* ── Course statistics ────────────────────────────────────────── */}
        {stats && (
          <FadeUp delay={0.18} className="mb-6">
            <CourseStatistics stats={stats} />
          </FadeUp>
        )}

        {/* ── AI Study Tools ───────────────────────────────────────────── */}
        <FadeUp delay={0.24}>
          <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                <Sparkles className="h-4 w-4 text-primary" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">AI Study Tools</h3>
                <p className="text-xs text-muted-foreground">
                  Select chapters, then generate a quiz or notes
                </p>
              </div>
            </div>

            <div className="mb-6">
              <ChapterSelect
                chapters={course.chapters}
                selectedChapters={selectedChapters}
                onSelectionChange={setSelectedChapters}
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                onClick={handleGenerateQuiz}
                size="sm"
                className="gap-2 bg-primary text-xs font-semibold text-primary-foreground
                  hover:bg-primary/90 glow-primary-sm"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Generate Quiz
              </Button>
              <Button
                onClick={handleGenerateNotes}
                variant="outline"
                size="sm"
                className="gap-2 border-border/60 bg-card/50 text-xs backdrop-blur-sm
                  hover:border-primary/30 hover:bg-card"
              >
                <FileText className="h-3.5 w-3.5" />
                Generate Notes
              </Button>
            </div>
          </div>
        </FadeUp>
      </main>

      <Footer />
    </div>
  );
};

export default CoursePage;
