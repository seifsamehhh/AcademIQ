"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import {
  api,
  ApiAuthError,
  clearAuthStorage,
  getAccessToken,
  getStoredStudentId,
  getStoredStudentName,
} from "@/lib/api";
import type { DemoCourseResult, StudentResults } from "@/lib/types";
import { ApiErrorAlert } from "@/components/common/ApiErrorAlert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function courseGradeDisplay(course: DemoCourseResult): {
  primary: string;
  secondary?: string;
} {
  const available =
    course.gradeAvailable === true ||
    (course.gradeAvailable !== false && course.grade != null);

  if (!available) {
    return {
      primary: "Not available",
      secondary: course.gradeNote ?? "Moodle grade data has not been synced yet.",
    };
  }

  return {
    primary: String(course.grade),
    secondary: course.gradeLabel ?? undefined,
  };
}

export default function DashboardPage() {
  const router = useRouter();
  const [studentId, setStudentId] = useState<string | null>(null);
  const [studentName, setStudentName] = useState<string | null>(null);
  const [results, setResults] = useState<StudentResults | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    const id = getStoredStudentId();
    if (!token || !id) {
      router.replace("/signin");
      return;
    }
    setStudentId(id);
    setStudentName(getStoredStudentName());

    let active = true;
    setError("");
    api
      .getStudentResults(id)
      .then((data) => {
        if (active) setResults(data);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiAuthError) {
          clearAuthStorage();
          router.replace("/signin?expired=1");
          return;
        }
        setError("Could not load your results. Please try again.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [router]);

  if (!studentId) {
    return (
      <div className="flex flex-1 items-center justify-center py-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const displayName = results?.name ?? studentName ?? "Student";
  const signedInAs = results?.loginEmail || studentId;
  const hasResults = Boolean(results?.name);
  const gpaUnavailable = results?.gpaAvailable !== true;

  const riskLabel =
    results?.riskAvailable === false
      ? "Not enough data"
      : results?.risk ?? "Not enough data";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Welcome, {displayName}
        </h1>
        <p className="text-muted-foreground">
          Signed in as <span className="font-medium">{signedInAs}</span>
          {results?.dataSource === "synced" && results.lastSync ? (
            <>
              {" "}
              · Last Moodle sync{" "}
              {new Date(results.lastSync).toLocaleString()}
            </>
          ) : null}
        </p>
      </div>

      {error ? <ApiErrorAlert message={error} /> : null}

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : hasResults ? (
        <>
          <div className="grid gap-6 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-muted-foreground">
                  GPA
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-foreground">
                  {gpaUnavailable ? "GPA not available yet" : results!.gpa}
                </p>
                {gpaUnavailable && results?.gpaNote ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {results.gpaNote}
                  </p>
                ) : results?.gpaSource ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {results.gpaSource}
                  </p>
                ) : null}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-muted-foreground">
                  Risk Level
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-foreground">
                  {riskLabel}
                </p>
                {results?.riskNote ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {results.riskNote}
                  </p>
                ) : results?.riskSource ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {results.riskSource}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Courses &amp; Grades</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="divide-y divide-border">
                {(results!.courses ?? []).map((course) => {
                  const grade = courseGradeDisplay(course);
                  return (
                    <li
                      key={course.courseId ?? course.name}
                      className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0"
                    >
                      <span className="font-medium text-foreground">
                        {course.name}
                      </span>
                      <div className="text-right">
                        <span
                          className={
                            grade.primary === "Not available"
                              ? "text-sm font-medium text-muted-foreground"
                              : "text-lg font-semibold text-primary"
                          }
                        >
                          {grade.primary}
                        </span>
                        {grade.secondary ? (
                          <p className="mt-1 text-xs text-muted-foreground max-w-[220px]">
                            {grade.secondary}
                          </p>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No results found for this student.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
