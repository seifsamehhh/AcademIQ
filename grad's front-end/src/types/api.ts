/**
 * api.ts — TypeScript types for AcademIQ backend API responses.
 *
 * Mirrors the Pydantic models in:
 *   backend/app/api/auth.py
 *   backend/app/api/student.py
 *   backend/app/api/extension.py
 */

// ── Auth ───────────────────────────────────────────────────────────────────

export interface LoginResponse {
  token:      string;
  student_id: string;
  username:   string;
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export interface PerformancePoint {
  date:  string;
  score: number;
}

export interface CoursePredictionAPI {
  courseId:   string;
  courseName: string;
  score:      number;
  trend:      "up" | "down" | "flat";
}

export interface EngagementPoint {
  day:   string;
  hours: number;
}

export interface QuickStats {
  enrolled_courses: number;
  pending_tasks:    number;
  upcoming_quizzes: number;
}

export interface DashboardData {
  student_id:         string;
  username:           string;
  /** "live" when Chrome extension has synced real data; "mock" otherwise. */
  data_source:        "live" | "mock";
  avg_score:          number;
  overall_status:     "At Risk" | "Good" | "Perfect";
  weekly_performance: PerformancePoint[];
  course_predictions: CoursePredictionAPI[];
  study_engagement:   EngagementPoint[];
  burnout_risk:       boolean;
  quick_stats:        QuickStats;
}

// ── Insights ───────────────────────────────────────────────────────────────

export interface Recommendation {
  title:       string;
  description: string;
  priority:    "High" | "Medium" | "Low";
}

export interface ProgressPoint {
  week:       string;
  engagement: number;
  quiz:       number;
  predicted:  number;
}

export interface TimelineEntry {
  week: string;
  text: string;
  tone: "warning" | "success" | "info";
}

export interface InsightsData {
  student_id:       string;
  data_source:      "live" | "mock";
  classification:   "High Performer" | "Average Performer" | "At Risk";
  confidence:       number;
  pass_probability: number;
  risk_level:       "LOW" | "MEDIUM" | "HIGH";
  engagement_score: number;
  strengths:        string[];
  weaknesses:       string[];
  recommendations:  Recommendation[];
  progress_data:    ProgressPoint[];
  timeline:         TimelineEntry[];
}
