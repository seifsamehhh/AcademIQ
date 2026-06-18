"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { CourseInsights } from "@/lib/types";
import { PerformanceClassification } from "@/components/insights/PerformanceClassification";
import { RiskFactors } from "@/components/insights/RiskFactors";
import { ApiErrorAlert } from "@/components/common/ApiErrorAlert";
import { Skeleton } from "@/components/ui/skeleton";

function InsightsContent() {
  const searchParams = useSearchParams();
  const courseParam = searchParams.get("course");
  const [insights, setInsights] = useState<CourseInsights | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setError("");
      try {
        let courseId = courseParam;
        if (!courseId) {
          const courses = await api.getCourses();
          courseId = courses[0]?.id ?? "";
        }
        if (!courseId) {
          if (active) setError("No courses found yet. Sync Moodle data first.");
          return;
        }
        const data = await api.getInsights(courseId);
        if (active) setInsights(data);
      } catch {
        if (active) {
          setError("Could not load insights. Please sign in again or refresh the page.");
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [courseParam]);

  const ruleBased = insights?.heuristic === true;

  return (
    <div className="space-y-6">
      <Link
        href="/performance"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Performance Analysis
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-foreground">Performance guidance</h1>
        <p className="text-muted-foreground">
          {insights
            ? `${insights.course.code} — ${insights.course.name}`
            : "Loading course guidance..."}
        </p>
      </div>

      {error ? <ApiErrorAlert message={error} /> : null}

      {insights ? (
        <>
          <PerformanceClassification
            isHighPerformer={insights.isHighPerformer}
            summary={insights.classificationSummary}
            ruleBased={ruleBased}
            performanceStatus={insights.performanceStatus}
          />
          <RiskFactors factors={insights.riskFactors} ruleBased={ruleBased} />
        </>
      ) : (
        <>
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </>
      )}
    </div>
  );
}

export default function InsightsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <InsightsContent />
    </Suspense>
  );
}
