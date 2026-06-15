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
import type { StudentResults } from "@/lib/types";
import { ApiErrorAlert } from "@/components/common/ApiErrorAlert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

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
  const hasResults = Boolean(results?.name);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Welcome, {displayName}
        </h1>
        <p className="text-muted-foreground">
          Signed in as <span className="font-medium">{studentId}</span>
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
                  {results!.gpa ?? "—"}
                </p>
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
                  {results!.risk}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Courses &amp; Grades</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="divide-y divide-border">
                {(results!.courses ?? []).map((course) => (
                  <li
                    key={course.courseId ?? course.name}
                    className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                  >
                    <span className="font-medium text-foreground">
                      {course.name}
                    </span>
                    <span className="text-lg font-semibold text-primary">
                      {course.grade != null ? course.grade : "—"}
                    </span>
                  </li>
                ))}
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
