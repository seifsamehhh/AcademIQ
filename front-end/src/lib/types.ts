/**
 * Shared domain types for AcademIQ.
 *
 * These mirror the shapes returned by the FastAPI backend, which in turn
 * aggregates data scraped/integrated from Moodle plus the ML model outputs.
 * Keeping them in one place means the mock client and a future real client
 * stay interchangeable.
 */

import type { PerformanceFeature } from "./recommendations";

export interface Student {
  id: string;
  username: string;
  fullName: string;
}

/** Account roles. Drives redirects and route protection. */
export type Role = "admin" | "student";

/**
 * An authenticated AcademIQ account (admin or student). Mirrors the backend's
 * `serialize_user` output — note the password hash is never sent to the client.
 */
export interface AuthUser {
  id: string;
  fullName: string;
  email: string;
  role: Role;
  /** Moodle linkage identifiers (primary mapping keys; may be absent). */
  moodleUserId?: string | null;
  studentId?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** Result of a successful sign-in. */
export interface AuthResult {
  user: AuthUser;
  role: Role;
  /** Session token (also set as an httpOnly cookie by the backend). */
  token: string;
}

/** JWT login response from POST /api/auth/login. */
export interface LoginResult {
  access_token: string;
  token_type: string;
  student_id: string;
  name: string;
  role: Role;
}

/** A course row in student results. */
export interface DemoCourseResult {
  name: string;
  grade: number | null;
  courseId?: string;
  code?: string;
  source?: "moodle_sync" | "seeded" | string;
  lastSyncedAt?: string | null;
  activity?: {
    quizAttempts?: number;
    assignmentSubmissions?: number;
    timeSpentSeconds?: number;
    activitySource?: string;
  };
}

/** Academic results from GET /student/{student_id}/results. */
export interface StudentResults {
  name?: string;
  loginEmail?: string;
  gpa?: number | null;
  gpaAvailable?: boolean;
  gpaNote?: string | null;
  risk?: string;
  courses?: DemoCourseResult[];
  dataSource?: "synced" | "demo" | "metrics_only" | "none";
  lastSync?: string | null;
  averageScore?: number | null;
}

/** Payload for an admin creating or editing a user. */
export interface UserInput {
  fullName: string;
  email: string;
  role: Role;
  moodleUserId?: string | null;
  studentId?: string | null;
  /** Optional on create; if omitted the backend generates a secure password. */
  password?: string;
}

/** Admin mutation result; `generatedPassword` is present only when generated. */
export interface UserMutationResult {
  user: AuthUser;
  generatedPassword?: string;
}

export interface Course {
  id: string;
  name: string;
  /** Short code shown in compact UI, e.g. "CS204". */
  code: string;
  source?: "moodle_sync" | "seeded" | string;
  lastSyncedAt?: string | null;
}

/** Four-level burnout classification from the burnout-detection model. */
export type BurnoutLevel = "Safe" | "Low Risk" | "Medium Risk" | "High Risk";

/** Categorical label from the student-clustering model. */
export type PerformanceStatus = "Good" | "Average" | "At Risk";

/** Dashboard quick-statistics card (across ALL enrolled courses). */
export interface DashboardStats {
  /** Average score across all instructor-graded Moodle tasks (0-100). */
  averageScore: number;
  /** Average task-completion percentage (0-100). */
  averageCompletion: number;
  enrolledCourses: number;
}

/** A single point on the weekly study-time trend (last 3 weeks). */
export interface StudyTimePoint {
  /** Human label for the week, e.g. "Week of May 12". */
  label: string;
  /** Study time for that week, in hours. */
  hours: number;
}

/** Burnout card data — derived from TOTAL study time across all courses. */
export interface BurnoutStatus {
  level: BurnoutLevel;
  message: string;
}

export interface DashboardData {
  student: Student;
  stats: DashboardStats;
  studyTime: StudyTimePoint[];
  burnout: BurnoutStatus;
}

/** Breakdown of a task type (quizzes or assignments) within a course. */
export interface TaskBreakdown {
  attempted: number;
  total: number;
  /** Average score on attempted tasks (0-100); null when no graded items yet. */
  averageScore: number | null;
}

/** Per-course statistics shown on the Performance Analysis page. */
export interface CourseStatistics {
  quizzes: TaskBreakdown;
  assignments: TaskBreakdown;
  /** Total time spent on the course, in hours. */
  totalTimeHours: number;
  /** Weekly-average study time; null when no time data exists. */
  weeklyAverageHours: number | null;
  /** True when weekly average is approximated, not from Moodle weekly logs. */
  weeklyAverageEstimated?: boolean;
}

export type ActivityDataSource = "seeded" | "synced" | "none";

/** Course-scoped output combining grade prediction + clustering + actuals. */
export interface PerformanceAnalysis {
  course: Course;
  /** Numeric grade from ML when available; null when ML is not deployed. */
  predictedGrade: number | null;
  /** Categorical status from ML when available; null otherwise. */
  status: PerformanceStatus | null;
  /** Actual Moodle average (0-100); null when no grade data exists. */
  courseAverage: number | null;
  hasGradeData?: boolean;
  statistics: CourseStatistics;
  /** "ml" when a model produced the prediction; otherwise "fallback". */
  engine?: "ml" | "fallback";
  mlAvailable?: boolean;
  message?: string | null;
  heuristic?: boolean;
  /** Whether activity stats are seeded demo data, Moodle sync, or unavailable. */
  activityDataSource?: ActivityDataSource;
  /** Human-readable note about the activity stats data source. */
  activityStatsNote?: string;
}

/**
 * A single ranked risk factor — a SHAP "negative driver" surfaced by
 * PerformanceModel_v4 (see `lib/recommendations.ts`).
 */
export interface RiskFactor {
  title: string;
  description: string;
  /** Relative impact on predicted performance (0-100), used for ranking. */
  impact: number;
  /**
   * The v4 behavioural feature this driver corresponds to, when known. Used to
   * resolve the model's canonical recommendation; the live backend may instead
   * send `recommendation` directly.
   */
  feature?: PerformanceFeature;
  /**
   * Actionable, model-generated guidance addressing this specific factor —
   * the `action` text from the v4 recommendation map for `feature`.
   */
  recommendation: string;
}

/** Specific Insights page payload for a course. */
export interface CourseInsights {
  course: Course;
  /** Whether the student is currently a high performer for this course. */
  isHighPerformer: boolean;
  classificationSummary: string;
  /** Risk factors, expected pre-sorted by impact (highest first). */
  riskFactors: RiskFactor[];
  /** True when output is rule-based rather than from a deployed ML model. */
  heuristic?: boolean;
}

/** A learning material title scraped from Moodle, selectable for quiz gen. */
export interface LearningMaterial {
  id: string;
  title: string;
  /** e.g. "PDF", "Slides", "Notes". */
  kind: string;
  /** True when enough extracted text exists for quiz generation. */
  hasContent?: boolean;
  source?: "moodle_sync" | "seeded" | string;
  contentNote?: string | null;
  extractionStatus?: string | null;
  /**
   * Granular quiz-readiness classification:
   *   "ready"             — selectable, has extracted text
   *   "not_uploaded"      — listed from Moodle but not processed yet
   *   "extraction_failed" — text extraction failed
   *   "too_short"         — extracted text below minimum threshold
   *   "not_quiz_material" — grades / admin / forum / folder type
   */
  quizStatus?:
    | "ready"
    | "limited_ready"
    | "not_uploaded"
    | "extraction_failed"
    | "too_short"
    | "extraction_too_short"
    | "not_enough_readable_text"
    | "unsupported"
    | "not_quiz_material"
    | string;
  quizStatusReason?: string | null;
  /** True when the material is educational (lecture/lab/notes/slides/etc.) */
  isEducational?: boolean;
  isNonQuizMaterial?: boolean;
  /** Stored extracted text length from backend */
  contentTextLength?: number;
  /** True when backend verified quiz can be generated from this material alone */
  quizGenerationEligible?: boolean;
  readyForQuiz?: boolean;
  visibleInMainList?: boolean;
  visibleInOtherItems?: boolean;
  sortGroup?: number;
  sortNumber?: number;
  sortLinkRank?: number;
  materialKind?: string;
  materialNumber?: number;
  isLinkWrapper?: boolean;
  hasRealFileSibling?: boolean;
  questionCountPossible?: number;
  minQuestionsRequired?: number;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  /** Index into `options`. */
  correctIndex: number;
}

export interface GeneratedQuiz {
  courseId: string;
  /** Material ids the quiz was generated from. */
  materialIds: string[];
  questions: QuizQuestion[];
  /** Shown when a limited_ready material generated 3–4 questions. */
  limitedQuizNote?: string;
  /**
   * "selected_material_only" — content came from the chosen material alone.
   */
  generatorMode?: "selected_material_only" | string;
  engine?: string;
  debug?: {
    generator_mode?: string;
    selected_material_ids?: string[];
    selected_material_titles?: (string | null)[];
    context_material_ids_used?: string[];
    context_material_titles_used?: string[];
    reason?: string;
    total_content_chars?: number;
    question_count?: number;
    [key: string]: unknown;
  };
}
