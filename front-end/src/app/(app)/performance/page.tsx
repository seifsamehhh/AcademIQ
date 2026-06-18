"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { Course, PerformanceAnalysis } from "@/lib/types";
import { CourseSelect } from "@/components/common/CourseSelect";
import { ApiErrorAlert } from "@/components/common/ApiErrorAlert";
import { PredictedGradeCard } from "@/components/performance/PredictedGradeCard";
import { PerformanceStatusCard } from "@/components/performance/PerformanceStatusCard";
import { MlUnavailableCard } from "@/components/performance/MlUnavailableCard";
import { CourseAverageCard } from "@/components/performance/CourseAverageCard";
import { ActivityStatsNotice } from "@/components/performance/ActivityStatsNotice";
import { CourseStatistics } from "@/components/performance/CourseStatistics";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function PerformancePage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [analysis, setAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError("");
    api
      .getCourses()
      .then((list) => {
        if (!active) return;
        setCourses(list);
        if (list.length) setSelectedId(list[0].id);
      })
      .catch(() => {
        if (active) {
          setError("Could not load your courses. Please sign in again or refresh the page.");
        }
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    setAnalysis(null);
    api
      .getPerformance(selectedId)
      .then((data) => {
        if (active) setAnalysis(data);
      })
      .catch(() => {
        if (active) {
          setError("Could not load performance data for this course.");
        }
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const ready = analysis?.course.id === selectedId ? analysis : null;
  const mlReady = ready?.mlAvailable === true;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Performance Analysis</h1>
        <p className="text-muted-foreground">
          View course activity, actual grades, and ML predictions when available.
        </p>
      </div>

      {error ? (
        <ApiErrorAlert message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : null}

      {courses.length ? (
        <CourseSelect
          courses={courses}
          value={selectedId}
          onChange={setSelectedId}
        />
      ) : (
        <Skeleton className="h-16 w-full max-w-sm" />
      )}

      {ready ? (
        <div className="space-y-6">
          {mlReady ? (
            <div className="grid gap-6 md:grid-cols-2">
              <PredictedGradeCard
                grade={ready.predictedGrade}
                source={ready.classificationSource}
              />
              <PerformanceStatusCard
                status={ready.status}
                source={ready.classificationSource}
              />
            </div>
          ) : (
            <MlUnavailableCard
              message={
                ready.message ??
                "The model needs complete synced Moodle activity features before it can generate a reliable prediction."
              }
            />
          )}

          {mlReady ? (
            <Link
              href={`/insights?course=${ready.course.id}`}
              className={buttonVariants({ variant: "default" })}
            >
              View Insights
              <ArrowRight className="h-4 w-4" />
            </Link>
          ) : null}

          <CourseAverageCard
            courseAverage={ready.courseAverage}
            hasGradeData={ready.hasGradeData ?? ready.courseAverage !== null}
            predictedGrade={mlReady ? ready.predictedGrade : null}
          />
          <ActivityStatsNotice
            source={ready.activityDataSource ?? "none"}
            note={
              ready.activityStatsNote ??
              "Activity stats are based on synced Moodle records available to AcademIQ."
            }
          />
          <CourseStatistics stats={ready.statistics} />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
          </div>
          <Skeleton className="h-44 w-full" />
        </div>
      )}
    </div>
  );
}
