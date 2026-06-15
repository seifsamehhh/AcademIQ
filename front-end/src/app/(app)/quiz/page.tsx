"use client";

import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Course, GeneratedQuiz, LearningMaterial } from "@/lib/types";
import { CourseSelect } from "@/components/common/CourseSelect";
import { ApiErrorAlert } from "@/components/common/ApiErrorAlert";
import { MaterialSelect } from "@/components/quiz/MaterialSelect";
import { QuizView } from "@/components/quiz/QuizView";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

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
        const readyIds = new Set(
          list.filter((m) => m.hasContent).map((m) => m.id),
        );
        setSelectedMaterials((prev) => prev.filter((id) => readyIds.has(id)));
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
    if (!material?.hasContent) return;
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
    } catch {
      setQuiz(null);
      setError(
        "Quiz generation failed. Please try another material or try again later.",
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Quiz Generation</h1>
        <p className="text-muted-foreground">
          Pick a course, choose materials with &quot;Ready for quiz&quot;, then generate.
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
    </div>
  );
}
