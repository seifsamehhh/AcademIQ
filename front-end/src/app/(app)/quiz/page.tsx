"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Course, GeneratedQuiz, LearningMaterial } from "@/lib/types";
import { CourseSelect } from "@/components/common/CourseSelect";
import { ApiErrorAlert } from "@/components/common/ApiErrorAlert";
import { MaterialSelect } from "@/components/quiz/MaterialSelect";
import { QuizView } from "@/components/quiz/QuizView";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ── Debug panel (only rendered when NEXT_PUBLIC_QUIZ_DEBUG=true) ──────────────

function sortGroupLabel(m: LearningMaterial): string {
  if (m.quizStatus === "not_quiz_material") return "5-NonQuiz";
  const t = (m.title || "").toLowerCase();
  if (/\blecture|\blec\s*\d/i.test(t)) return "0-Lecture";
  if (/\blab\b|\blab\s*\d/i.test(t)) return "1-Lab";
  if (/\b(revision|review|summary)\b/i.test(t)) return "2-Revision";
  if (/\b(notes?|tutorial|handout|slides?|worksheet|chapter|exercise|module)\b/i.test(t)) return "3-Notes";
  return "4-Other";
}

function extractNumDbg(s: string): number {
  const m = s.match(/\d+/);
  return m ? parseInt(m[0], 10) : 9999;
}

function QuizDebugPanel({
  courseId,
  materials,
  quiz,
}: {
  courseId: string;
  materials: LearningMaterial[] | null;
  quiz: GeneratedQuiz | null;
}) {
  const [open, setOpen] = useState(false);
  const apiUrl = `/courses/${courseId}/materials`;

  if (!materials) return null;

  const sorted = [...materials].sort((a, b) => {
    const ga = sortGroupLabel(a).charCodeAt(0) - sortGroupLabel(b).charCodeAt(0);
    if (ga !== 0) return ga;
    return extractNumDbg(a.title) - extractNumDbg(b.title);
  });

  const educational = materials.filter((m) => m.quizStatus !== "not_quiz_material");
  const nonQuiz = materials.filter((m) => m.quizStatus === "not_quiz_material");

  return (
    <div className="mt-4 rounded-lg border border-dashed border-border bg-muted/30 text-xs">
      <button
        type="button"
        className="flex w-full items-center gap-2 p-3 text-left text-muted-foreground hover:text-foreground"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="font-mono font-medium">
          [Debug] API: {apiUrl} · {materials.length} materials returned
          ({educational.length} educational, {nonQuiz.length} non-quiz)
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-border p-3">
          {/* Materials table */}
          <div>
            <p className="mb-1 font-semibold text-foreground">
              First 12 materials (sorted as UI would show):
            </p>
            <table className="w-full text-left">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="pr-2">Title</th>
                  <th className="pr-2">sort_group</th>
                  <th className="pr-2">sort_num</th>
                  <th className="pr-2">status</th>
                  <th>selectable</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {sorted.slice(0, 12).map((m) => (
                  <tr key={m.id} className="border-t border-border/40">
                    <td className="py-0.5 pr-2 max-w-[220px] truncate">{m.title}</td>
                    <td className="pr-2">{sortGroupLabel(m)}</td>
                    <td className="pr-2">{extractNumDbg(m.title)}</td>
                    <td className="pr-2">{m.quizStatus ?? "–"}</td>
                    <td>{m.quizStatus === "ready" || m.quizStatus === "extraction_too_short" ? "✓" : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Quiz debug info */}
          {quiz && (
            <div className="border-t border-border pt-2">
              <p className="mb-1 font-semibold text-foreground">Last generated quiz debug:</p>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all text-[11px] text-muted-foreground">
                {JSON.stringify(
                  {
                    generator_mode: quiz.generatorMode,
                    engine: quiz.engine,
                    selected_ids: quiz.debug?.selected_material_ids,
                    selected_titles: quiz.debug?.selected_material_titles,
                    context_titles: quiz.debug?.context_material_titles_used,
                    context_selection_reason: quiz.debug?.context_selection_reason,
                    duplicate_guard: quiz.debug?.duplicate_guard_triggered,
                    content_length: quiz.debug?.selected_material_content_length,
                    question_count: quiz.questions?.length,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Hidden unless NEXT_PUBLIC_QUIZ_DEBUG=true (does not clutter demo UI).
const QUIZ_DEBUG = process.env.NEXT_PUBLIC_QUIZ_DEBUG === "true";

function isMaterialSelectable(m: LearningMaterial): boolean {
  if (m.quizStatus === "not_quiz_material") return false;
  if (m.quizGenerationEligible === true) return true;
  if (m.quizStatus === "ready") return true;
  if (m.quizStatus === "extraction_too_short") return true;
  return false;
}

export default function QuizPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState("");
  const [materials, setMaterials] = useState<LearningMaterial[] | null>(null);
  const [selectedMaterials, setSelectedMaterials] = useState<string[]>([]);
  const [quiz, setQuiz] = useState<GeneratedQuiz | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setError("");
    api
      .getCourses()
      .then((list) => {
        if (!active) return;
        setCourses(list);
        if (list.length) setSelectedCourse(list[0].id);
      })
      .catch(() => {
        if (active) {
          setError("Could not load your courses. Please sign in again or refresh the page.");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCourse) return;
    let active = true;
    api
      .getMaterials(selectedCourse)
      .then((list) => {
        if (!active) return;
        setMaterials(list);
        const selectableIds = new Set(
          list.filter(isMaterialSelectable).map((m) => m.id),
        );
        setSelectedMaterials((prev) => prev.filter((id) => selectableIds.has(id)));
      })
      .catch(() => {
        if (active) setMaterials([]);
      });
    return () => {
      active = false;
    };
  }, [selectedCourse]);

  // Switching course clears the downstream selection + any generated quiz.
  const handleCourseChange = (id: string) => {
    setSelectedCourse(id);
    setMaterials(null);
    setSelectedMaterials([]);
    setQuiz(null);
  };

  const toggleMaterial = (id: string) => {
    const material = materials?.find((m) => m.id === id);
    if (!material || !isMaterialSelectable(material)) return;
    setQuiz(null);
    setError("");
    setSelectedMaterials((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id],
    );
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError("");
    try {
      const generated = await api.generateQuiz(selectedCourse, selectedMaterials);
      setQuiz(generated);
    } catch (err) {
      setQuiz(null);
      const msg = err instanceof Error ? err.message : String(err);
      // msg is already the backend's detail.message or detail string
      setError(msg || "Quiz generation failed. Please try another material or try again later.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Quiz Generation</h1>
        <p className="text-muted-foreground">
          Pick a course, select any uploaded material, then generate. Works with
          lectures, labs, revisions, slides, and any uploaded PDF or PPTX.
          Use the Chrome extension → &quot;Upload materials for quiz&quot; on a Moodle course page first.
        </p>
      </div>

      {error ? <ApiErrorAlert message={error} /> : null}

      {courses.length ? (
        <CourseSelect
          courses={courses}
          value={selectedCourse}
          onChange={handleCourseChange}
        />
      ) : (
        <Skeleton className="h-16 w-full max-w-sm" />
      )}

      {materials ? (
        <MaterialSelect
          materials={materials}
          selectedIds={selectedMaterials}
          onToggle={toggleMaterial}
        />
      ) : (
        <Skeleton className="h-48 w-full" />
      )}

      <Button
        onClick={handleGenerate}
        disabled={selectedMaterials.length === 0 || isGenerating}
      >
        {isGenerating ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Generating...
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4" />
            Generate Quiz
          </>
        )}
      </Button>

      {quiz && <QuizView quiz={quiz} />}

      {QUIZ_DEBUG && (
        <QuizDebugPanel
          courseId={selectedCourse}
          materials={materials}
          quiz={quiz}
        />
      )}
    </div>
  );
}
