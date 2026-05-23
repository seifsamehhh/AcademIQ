import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import Footer from "@/components/layout/Footer";
import { useUser } from "@/context/UserContext";
import { courses, quizGrades } from "@/data/mockData";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Award, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

// Colour based on percentage band
const scoreStyle = (pct: number) => {
  if (pct >= 85) return { text: "text-emerald-400", bar: "bg-emerald-400", glow: "shadow-[0_0_16px_hsl(142_72%_50%/0.25)]" };
  if (pct >= 70) return { text: "text-sky-400",     bar: "bg-sky-400",     glow: "shadow-[0_0_16px_hsl(199_89%_50%/0.25)]" };
  if (pct >= 55) return { text: "text-amber-400",   bar: "bg-amber-400",   glow: "" };
  return               { text: "text-destructive",  bar: "bg-destructive", glow: "" };
};

// ── Quiz card ──────────────────────────────────────────────────────────────────
const QuizCard = ({
  quiz,
  idx,
}: {
  quiz: { quizName: string; score: number; totalMarks: number; date: string };
  idx: number;
}) => {
  const pct = Math.round((quiz.score / quiz.totalMarks) * 100);
  const s = scoreStyle(pct);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ delay: idx * 0.06, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm transition-all",
        "hover:border-border/80 hover:bg-card/80",
        s.glow
      )}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left */}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <Award className="h-4 w-4 text-primary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{quiz.quizName}</p>
            <p className="text-xs text-muted-foreground">{quiz.date}</p>
          </div>
        </div>

        {/* Score */}
        <div className="text-right shrink-0">
          <p className={cn("text-2xl font-bold tabular leading-none", s.text)}>
            {quiz.score}
            <span className="text-sm font-normal text-muted-foreground">/{quiz.totalMarks}</span>
          </p>
          <p className={cn("mt-0.5 text-xs font-medium tabular", s.text)}>{pct}%</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-4 h-1 w-full overflow-hidden rounded-full bg-muted/40">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ delay: idx * 0.06 + 0.2, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className={cn("h-full rounded-full", s.bar)}
        />
      </div>
    </motion.div>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────
const Grades = () => {
  const { username } = useUser();
  const [selectedCourse, setSelectedCourse] = useState<string>("");

  const grades = selectedCourse ? quizGrades[selectedCourse] ?? [] : [];

  // Compute course average
  const avg = grades.length
    ? Math.round(grades.reduce((s, q) => s + (q.score / q.totalMarks) * 100, 0) / grades.length)
    : null;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Spotlight */}
      <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-50" />

      <DashboardHeader username={username || "Student"} />

      <main className="container relative flex-1 py-8">
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8"
        >
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Assessment Results
          </p>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">Grades</h1>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Quiz results by course — select a course to load your scores.
              </p>
            </div>

            {/* Course selector */}
            <Select value={selectedCourse} onValueChange={setSelectedCourse}>
              <SelectTrigger
                className="h-9 w-[280px] border-border/60 bg-card/50 text-sm backdrop-blur-sm
                  focus:border-primary/50 focus:ring-1 focus:ring-primary/30"
              >
                <SelectValue placeholder="Select a course…" />
                <ChevronDown className="h-3.5 w-3.5 opacity-50" />
              </SelectTrigger>
              <SelectContent className="border-border/60 bg-card/95 backdrop-blur-xl">
                {courses.map((course) => (
                  <SelectItem key={course.id} value={course.id} className="text-sm">
                    <span className="font-medium">{course.code}</span>
                    <span className="ml-1.5 text-muted-foreground">— {course.name}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </motion.div>

        {/* Average banner — only when a course is selected */}
        <AnimatePresence>
          {selectedCourse && avg !== null && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="mb-5 overflow-hidden"
            >
              <div className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/50 px-5 py-3 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">Course average</span>
                <span className={cn("text-lg font-bold tabular", scoreStyle(avg).text)}>
                  {avg}%
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Grade cards */}
        <AnimatePresence mode="wait">
          {selectedCourse ? (
            grades.length > 0 ? (
              <motion.div
                key={selectedCourse}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="space-y-3"
              >
                {grades.map((quiz, idx) => (
                  <QuizCard key={`${quiz.quizName}-${idx}`} quiz={quiz} idx={idx} />
                ))}
              </motion.div>
            ) : (
              <motion.div
                key="no-grades"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="rounded-xl border border-dashed border-border/50 px-6 py-16 text-center"
              >
                <Award className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No quiz grades found for this course.</p>
              </motion.div>
            )
          ) : (
            <motion.div
              key="placeholder"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="rounded-xl border border-dashed border-border/40 px-6 py-20 text-center"
            >
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/5 ring-1 ring-primary/20">
                <Award className="h-5 w-5 text-primary/60" />
              </div>
              <p className="text-sm font-medium text-foreground">Select a course above</p>
              <p className="mt-1 text-xs text-muted-foreground">Your quiz grades will appear here.</p>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <Footer />
    </div>
  );
};

export default Grades;
