import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import Footer from "@/components/layout/Footer";
import { useUser } from "@/context/UserContext";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import {
  Sparkles, Download, Copy, ArrowLeft,
  CheckCircle2, BookOpen,
} from "lucide-react";
import { courses, noteContentBank, type NoteContent } from "@/data/mockData";

const buildMarkdown = (n: NoteContent) =>
  [
    `# ${n.title}`,
    "",
    `> ${n.summary}`,
    "",
    "## Key Highlights",
    ...n.keyPoints.map((k) => `- ${k}`),
    "",
    ...n.sections.flatMap((s) => [`## ${s.heading}`, "", s.body, ""]),
  ].join("\n");

// ── Component ──────────────────────────────────────────────────────────────────
const GeneratedNotes = () => {
  const { username } = useUser();
  const { toast }    = useToast();
  const navigate     = useNavigate();
  const location     = useLocation();
  const contentRef   = useRef<HTMLDivElement>(null);

  const stateCourseId = (location.state as { courseId?: string } | null)?.courseId;
  const stateChapters = (location.state as { chapters?: string[] } | null)?.chapters;

  const courseId = stateCourseId && noteContentBank[stateCourseId] ? stateCourseId : "cs101";
  const course   = courses.find((c) => c.id === courseId)!;
  const note     = noteContentBank[courseId];

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 700);
    return () => clearTimeout(t);
  }, []);

  const md = useMemo(() => buildMarkdown(note), [note]);

  const handleDownload = () => {
    const blob = new Blob([md], { type: "text/markdown" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `${note.title.replace(/\s+/g, "_")}.md`;
    a.click();
    URL.revokeObjectURL(url);
    toast({ title: "Notes downloaded", description: "Saved as Markdown." });
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(md);
      toast({ title: "Copied to clipboard" });
    } catch {
      toast({ title: "Copy failed", variant: "destructive" });
    }
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
          <div className="min-w-0">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-primary/25
              bg-primary/8 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3 w-3" /> AI-Generated Notes
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">{note.title}</h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {course.code} · {course.name}
              {stateChapters?.length ? <> · Chapters: {stateChapters.join(", ")}</> : null}
            </p>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(-1)}
              className="gap-1.5 border-border/60 bg-card/50 text-xs backdrop-blur-sm"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-1.5 border-border/60 bg-card/50 text-xs backdrop-blur-sm
                hover:border-primary/30"
            >
              <Copy className="h-3.5 w-3.5" /> Copy
            </Button>
            <Button
              size="sm"
              onClick={handleDownload}
              className="gap-1.5 bg-primary text-xs text-primary-foreground
                hover:bg-primary/90 glow-primary-sm"
            >
              <Download className="h-3.5 w-3.5" /> Download .md
            </Button>
          </div>
        </motion.div>

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 rounded-xl" />
            <Skeleton className="h-56 rounded-xl" />
            <Skeleton className="h-72 rounded-xl" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="grid gap-4 lg:grid-cols-[1fr_240px]"
          >
            {/* ── Main article ───────────────────────────────────────── */}
            <article
              ref={contentRef}
              className="rounded-xl border border-border/50 bg-card/50 p-7 backdrop-blur-sm
                lg:max-h-[calc(100vh-200px)] lg:overflow-y-auto"
            >
              {/* AI Summary */}
              <section className="mb-7">
                <div className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase
                  tracking-wider text-primary">
                  <Sparkles className="h-3.5 w-3.5" /> AI Summary
                </div>
                <p className="text-sm leading-relaxed text-foreground">{note.summary}</p>
              </section>

              <hr className="my-7 border-border/40" />

              {/* Key highlights */}
              <section className="mb-7">
                <h2 className="mb-4 text-base font-bold text-foreground">Key Highlights</h2>
                <ul className="space-y-2.5">
                  {note.keyPoints.map((k, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span className="text-sm leading-relaxed text-foreground">{k}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <hr className="my-7 border-border/40" />

              {/* Content sections */}
              <div className="space-y-7">
                {note.sections.map((s, i) => (
                  <section key={i}>
                    <h2 className="mb-3 text-base font-bold text-foreground">{s.heading}</h2>
                    <p className="text-sm leading-7 text-muted-foreground">{s.body}</p>
                    {i < note.sections.length - 1 && (
                      <hr className="mt-7 border-border/40" />
                    )}
                  </section>
                ))}
              </div>
            </article>

            {/* ── TOC sidebar ─────────────────────────────────────────── */}
            <aside className="rounded-xl border border-border/50 bg-card/50 p-4 backdrop-blur-sm
              h-fit lg:sticky lg:top-20">
              <div className="mb-3 flex items-center gap-2">
                <BookOpen className="h-3.5 w-3.5 text-primary" />
                <h3 className="text-xs font-semibold text-foreground">In this document</h3>
              </div>

              <ul className="space-y-1.5 text-xs">
                <li className="cursor-default text-muted-foreground transition-colors hover:text-foreground">
                  AI Summary
                </li>
                <li className="cursor-default text-muted-foreground transition-colors hover:text-foreground">
                  Key Highlights
                </li>
                {note.sections.map((s, i) => (
                  <li
                    key={i}
                    className="cursor-default pl-2 text-muted-foreground/70 transition-colors hover:text-foreground"
                  >
                    {s.heading}
                  </li>
                ))}
              </ul>

              <div className="mt-5 rounded-lg border border-border/40 bg-muted/20 p-3">
                <p className="mb-1 text-xs font-semibold text-foreground">{course.code}</p>
                <p className="text-xs text-muted-foreground">{course.name}</p>
              </div>
            </aside>
          </motion.div>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default GeneratedNotes;
