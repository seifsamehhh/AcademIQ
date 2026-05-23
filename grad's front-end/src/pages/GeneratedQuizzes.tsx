import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import Footer from "@/components/layout/Footer";
import { useUser } from "@/context/UserContext";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  ArrowLeft, ArrowRight, CheckCircle2,
  Clock, Sparkles, Send, RotateCcw,
} from "lucide-react";
import { courses, quizQuestionBank, type QuizQuestion } from "@/data/mockData";

const formatTime = (s: number) => {
  const m   = Math.floor(s / 60);
  const sec = s % 60;
  return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
};

// ── Component ──────────────────────────────────────────────────────────────────
const GeneratedQuizzes = () => {
  const { username } = useUser();
  const { toast }    = useToast();
  const navigate     = useNavigate();
  const location     = useLocation();

  const stateCourseId = (location.state as { courseId?: string } | null)?.courseId;
  const stateChapters = (location.state as { chapters?: string[] } | null)?.chapters;

  const courseId  = stateCourseId && quizQuestionBank[stateCourseId] ? stateCourseId : "cs101";
  const course    = courses.find((c) => c.id === courseId)!;
  const questions: QuizQuestion[] = quizQuestionBank[courseId];

  const [loading,    setLoading]    = useState(true);
  const [current,    setCurrent]    = useState(0);
  const [answers,    setAnswers]    = useState<Record<string, number>>({});
  const [submitted,  setSubmitted]  = useState(false);
  const [seconds,    setSeconds]    = useState(15 * 60);

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (loading || submitted) return;
    const i = setInterval(() => setSeconds((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(i);
  }, [loading, submitted]);

  useEffect(() => {
    if (seconds === 0 && !submitted) {
      setSubmitted(true);
      toast({ title: "Time's up", description: "Quiz auto-submitted." });
    }
  }, [seconds, submitted, toast]);

  const score = useMemo(
    () => questions.reduce((acc, q) => acc + (answers[q.id] === q.correctIndex ? 1 : 0), 0),
    [answers, questions]
  );

  const answeredCount = Object.keys(answers).length;
  const progress      = Math.round((answeredCount / questions.length) * 100);
  const q             = questions[current];
  const critical      = seconds < 60 && !submitted;

  const select = (idx: number) => {
    if (submitted) return;
    setAnswers((a) => ({ ...a, [q.id]: idx }));
  };

  const submit = () => {
    setSubmitted(true);
    toast({ title: "Quiz submitted", description: `Score: ${score}/${questions.length}` });
  };

  const reset = () => {
    setAnswers({});
    setCurrent(0);
    setSubmitted(false);
    setSeconds(15 * 60);
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Spotlight */}
      <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-50" />

      <DashboardHeader username={username || "Student"} />

      <main className="container relative flex-1 py-8">

        {/* ── Header ─────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mb-6 flex flex-wrap items-start justify-between gap-4"
        >
          <div>
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-primary/25
              bg-primary/8 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3 w-3" /> AI-Generated Quiz
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {course.name}
            </h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {course.code} · {course.instructor}
              {stateChapters?.length ? <> · Chapters: {stateChapters.join(", ")}</> : null}
            </p>
          </div>

          {/* Timer */}
          <motion.div
            animate={critical ? { scale: [1, 1.02, 1] } : {}}
            transition={{ repeat: Infinity, duration: 1 }}
            className={cn(
              "flex items-center gap-2 rounded-xl border px-4 py-2.5 font-mono text-lg font-bold tabular",
              critical
                ? "border-destructive/50 bg-destructive/10 text-destructive"
                : "border-border/50 bg-card/50 text-foreground backdrop-blur-sm"
            )}
          >
            <Clock className="h-4 w-4" />
            {formatTime(seconds)}
          </motion.div>
        </motion.div>

        {loading ? (
          <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
            <Skeleton className="h-80 rounded-xl" />
            <Skeleton className="h-80 rounded-xl" />
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[220px_1fr]">

            {/* ── Sidebar question palette ────────────────────────────── */}
            <motion.aside
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="rounded-xl border border-border/50 bg-card/50 p-4 backdrop-blur-sm h-fit lg:sticky lg:top-20"
            >
              <p className="mb-3 text-xs font-semibold text-foreground">Questions</p>
              <div className="grid grid-cols-5 gap-1.5">
                {questions.map((qq, i) => {
                  const answered  = answers[qq.id] !== undefined;
                  const isCurrent = i === current;
                  const correct   = submitted && answers[qq.id] === qq.correctIndex;
                  const wrong     = submitted && answered && answers[qq.id] !== qq.correctIndex;
                  return (
                    <button
                      key={qq.id}
                      onClick={() => setCurrent(i)}
                      className={cn(
                        "h-8 w-8 rounded-lg border text-xs font-semibold transition-all",
                        isCurrent && "ring-2 ring-primary ring-offset-1 ring-offset-card",
                        correct  && "border-emerald-500/60 bg-emerald-500/20 text-emerald-400",
                        wrong    && "border-destructive/60 bg-destructive/15 text-destructive",
                        !submitted && answered  && "border-primary/50 bg-primary/15 text-primary",
                        !submitted && !answered && "border-border/50 text-muted-foreground hover:border-border"
                      )}
                    >
                      {i + 1}
                    </button>
                  );
                })}
              </div>

              <div className="mt-4 space-y-1.5 text-xs text-muted-foreground">
                <p className="tabular">{answeredCount}/{questions.length} answered</p>
                <Progress value={progress} className="h-1 bg-muted/40 [&>div]:bg-primary" />
              </div>

              {/* Score revealed after submit */}
              <AnimatePresence>
                {submitted && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-4 overflow-hidden rounded-lg border border-border/50 bg-muted/20 p-3 text-center"
                  >
                    <p className="text-xs text-muted-foreground">Score</p>
                    <p className="text-2xl font-bold tabular text-foreground">
                      {score}
                      <span className="text-sm font-normal text-muted-foreground">
                        /{questions.length}
                      </span>
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {Math.round((score / questions.length) * 100)}%
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.aside>

            {/* ── Question card ───────────────────────────────────────── */}
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="rounded-xl border border-border/50 bg-card/50 p-6 backdrop-blur-sm"
            >
              <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
                <span>Question {current + 1} of {questions.length}</span>
                <span className="tabular">{progress}% complete</span>
              </div>
              <Progress
                value={((current + 1) / questions.length) * 100}
                className="mb-6 h-1 bg-muted/40 [&>div]:bg-primary"
              />

              <h2 className="mb-6 text-lg font-semibold leading-relaxed text-foreground">
                {q.question}
              </h2>

              <div className="space-y-2.5">
                {q.options.map((opt, idx) => {
                  const selected  = answers[q.id] === idx;
                  const isCorrect = submitted && idx === q.correctIndex;
                  const isWrong   = submitted && selected && idx !== q.correctIndex;

                  return (
                    <button
                      key={idx}
                      onClick={() => select(idx)}
                      disabled={submitted}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl border p-4 text-left text-sm transition-all",
                        "hover:border-primary/40 hover:bg-primary/5",
                        selected  && !submitted && "border-primary/50 bg-primary/8",
                        isCorrect && "border-emerald-500/50 bg-emerald-500/10",
                        isWrong   && "border-destructive/50 bg-destructive/10",
                        !selected && !isCorrect && !isWrong && "border-border/40",
                        submitted && "cursor-default"
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold",
                          selected  && !submitted && "border-primary bg-primary text-primary-foreground",
                          isCorrect && "border-emerald-500 bg-emerald-500 text-white",
                          isWrong   && "border-destructive bg-destructive text-destructive-foreground",
                          !selected && !isCorrect && !isWrong && "border-border/60 text-muted-foreground"
                        )}
                      >
                        {String.fromCharCode(65 + idx)}
                      </span>
                      <span className="flex-1 text-foreground">{opt}</span>
                      {isCorrect && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
                    </button>
                  );
                })}
              </div>

              {/* Nav */}
              <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrent((c) => Math.max(0, c - 1))}
                  disabled={current === 0}
                  className="gap-1.5 border-border/60 bg-card/50 text-xs"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Previous
                </Button>

                <div className="flex gap-2">
                  {submitted ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={reset}
                        className="gap-1.5 border-border/60 bg-card/50 text-xs"
                      >
                        <RotateCcw className="h-3.5 w-3.5" /> Retake
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => navigate("/dashboard")}
                        className="gap-1.5 bg-primary text-xs text-primary-foreground
                          hover:bg-primary/90 glow-primary-sm"
                      >
                        Dashboard
                      </Button>
                    </>
                  ) : current === questions.length - 1 ? (
                    <Button
                      size="sm"
                      onClick={submit}
                      className="gap-1.5 bg-primary text-xs text-primary-foreground
                        hover:bg-primary/90 glow-primary-sm"
                    >
                      <Send className="h-3.5 w-3.5" /> Submit Quiz
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => setCurrent((c) => Math.min(questions.length - 1, c + 1))}
                      className="gap-1.5 bg-primary text-xs text-primary-foreground
                        hover:bg-primary/90 glow-primary-sm"
                    >
                      Next <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            </motion.section>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default GeneratedQuizzes;
