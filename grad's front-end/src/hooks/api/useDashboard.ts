/**
 * useDashboard.ts — React Query hook for the student dashboard endpoint.
 *
 * Calls GET /api/student/dashboard (requires bearer token from UserContext).
 * On any error (backend offline, 401, timeout) the hook falls back to
 * MOCK_FALLBACK so the dashboard is always renderable.
 *
 * data.data_source === "live"  → real Moodle data from Chrome extension
 * data.data_source === "mock"  → backend returned mock, or backend is offline
 */
import { useQuery } from "@tanstack/react-query";
import { apiGet }   from "@/lib/apiClient";
import type { DashboardData } from "@/types/api";

// ── Offline / pre-sync fallback (mirrors mockData.ts) ─────────────────────────
const MOCK_FALLBACK: DashboardData = {
  student_id:   "local",
  username:     "",
  data_source:  "mock",
  avg_score:    83.0,
  overall_status: "Good",
  weekly_performance: [
    { date: "Mon", score: 72 },
    { date: "Tue", score: 78 },
    { date: "Wed", score: 85 },
    { date: "Thu", score: 82 },
    { date: "Fri", score: 88 },
    { date: "Sat", score: 90 },
    { date: "Sun", score: 85 },
  ],
  course_predictions: [
    { courseId: "cs101",   courseName: "Introduction to Programming", score: 89, trend: "up"   },
    { courseId: "cs201",   courseName: "Data Structures",             score: 78, trend: "up"   },
    { courseId: "cs301",   courseName: "Database",                    score: 66, trend: "down" },
    { courseId: "cs401",   courseName: "Software Engineering",        score: 92, trend: "up"   },
    { courseId: "math201", courseName: "Linear Algebra",              score: 81, trend: "flat" },
    { courseId: "eng101",  courseName: "English",                     score: 88, trend: "up"   },
  ],
  study_engagement: [
    { day: "Mon", hours: 2.1 },
    { day: "Tue", hours: 2.4 },
    { day: "Wed", hours: 2.0 },
    { day: "Thu", hours: 3.5 },
    { day: "Fri", hours: 3.8 },
    { day: "Sat", hours: 2.5 },
    { day: "Sun", hours: 2.8 },
  ],
  burnout_risk: false,
  quick_stats:  { enrolled_courses: 6, pending_tasks: 8, upcoming_quizzes: 3 },
};

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useDashboard() {
  const query = useQuery<DashboardData, Error>({
    queryKey:  ["dashboard"],
    queryFn:   () => apiGet<DashboardData>("/api/student/dashboard"),
    retry:     false,            // don't hammer an offline backend
    staleTime: 5 * 60 * 1_000,  // 5 minutes
  });

  return {
    /** Always defined — falls back to MOCK_FALLBACK when backend is offline. */
    data:     query.data ?? MOCK_FALLBACK,
    isLoading: query.isLoading,
    /** True when the backend returned real Moodle data from the extension. */
    isLive:   query.data?.data_source === "live",
    error:    query.error,
  };
}
