/**
 * useInsights.ts — React Query hook for the ML insights endpoint.
 *
 * Calls GET /api/student/insights (requires bearer token from UserContext).
 * Falls back to MOCK_FALLBACK on any error so the insights page is always usable.
 */
import { useQuery } from "@tanstack/react-query";
import { apiGet }   from "@/lib/apiClient";
import type { InsightsData } from "@/types/api";

// ── Offline / pre-sync fallback ────────────────────────────────────────────────
const MOCK_FALLBACK: InsightsData = {
  student_id:       "local",
  data_source:      "mock",
  classification:   "High Performer",
  confidence:       87,
  pass_probability: 0.87,
  risk_level:       "LOW",
  engagement_score: 0.5,
  strengths: [
    "Strong quiz performance across modules",
    "High activity before exam periods",
    "Consistent attendance in live sessions",
  ],
  weaknesses: [
    "Late assignment submissions",
    "Inconsistent weekly study behavior",
    "Low interaction with reading materials",
  ],
  recommendations: [
    { title: "Review lecture materials regularly", description: "Spend 30 minutes daily revisiting recent lectures.",  priority: "High"   },
    { title: "Start assignments earlier",          description: "Begin work within 48 hours of assignment release.",   priority: "High"   },
    { title: "Practice more quizzes",              description: "Take at least two practice quizzes per week.",        priority: "Medium" },
    { title: "Increase study consistency",         description: "Maintain a steady weekly study schedule.",            priority: "Medium" },
    { title: "Maintain current engagement",        description: "Keep up your participation in discussions.",          priority: "Low"    },
  ],
  progress_data: [
    { week: "W1", engagement: 55, quiz: 60, predicted: 62 },
    { week: "W2", engagement: 60, quiz: 65, predicted: 66 },
    { week: "W3", engagement: 68, quiz: 70, predicted: 71 },
    { week: "W4", engagement: 72, quiz: 75, predicted: 76 },
    { week: "W5", engagement: 78, quiz: 80, predicted: 81 },
    { week: "W6", engagement: 82, quiz: 84, predicted: 85 },
    { week: "W7", engagement: 85, quiz: 88, predicted: 87 },
    { week: "W8", engagement: 88, quiz: 90, predicted: 89 },
  ],
  timeline: [
    { week: "Week 1", text: "Improve quiz participation",                 tone: "warning" },
    { week: "Week 2", text: "Submit assignments on time",                 tone: "warning" },
    { week: "Week 3", text: "Engagement improved by 15%",                tone: "success" },
    { week: "Week 4", text: "Quiz accuracy trending upward",             tone: "success" },
    { week: "Week 5", text: "Student behavior becoming more consistent", tone: "success" },
    { week: "Week 6", text: "Maintain current weekly pace",              tone: "info"    },
  ],
};

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useInsights() {
  const query = useQuery<InsightsData, Error>({
    queryKey:  ["insights"],
    queryFn:   () => apiGet<InsightsData>("/api/student/insights"),
    retry:     false,
    staleTime: 5 * 60 * 1_000,
  });

  return {
    /** Always defined — falls back to MOCK_FALLBACK when backend is offline. */
    data:      query.data ?? MOCK_FALLBACK,
    isLoading: query.isLoading,
    /** True when the backend ran ML on real Moodle data from the extension. */
    isLive:    query.data?.data_source === "live",
    error:     query.error,
  };
}
