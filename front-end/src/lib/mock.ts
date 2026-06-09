import type {
  AuthUser,
  Course,
  CourseInsights,
  DashboardData,
  GeneratedQuiz,
  LearningMaterial,
  PerformanceAnalysis,
  Role,
  Student,
  UserInput,
} from "./types";
import { recommendationFor } from "./recommendations";

/**
 * Mock data used by the API client until the FastAPI backend is wired up.
 * Shapes match `types.ts` exactly so swapping in the real client is seamless.
 */

export const mockStudent: Student = {
  id: "stu_1042",
  username: "khaled.21",
  fullName: "khaled hsaballah",
};

/* -------------------------------------------------------------------------- */
/* Auth + admin mock state                                                    */
/* -------------------------------------------------------------------------- */

/**
 * In-memory user store so the admin dashboard is fully interactive in mock
 * mode (create/edit/delete/reset persist for the session). Mirrors the
 * backend's serialized user shape.
 */
const nowIso = () => new Date().toISOString();

let mockUsers: AuthUser[] = [
  {
    id: "u_admin",
    fullName: "AcademIQ Admin",
    email: "admin@academiq.local",
    role: "admin",
    moodleUserId: null,
    studentId: null,
    createdAt: nowIso(),
    updatedAt: nowIso(),
  },
  {
    id: "u_1042",
    fullName: "Khaled Hsaballah",
    email: "khaled@academiq.local",
    role: "student",
    moodleUserId: "55012",
    studentId: "S20210042",
    createdAt: nowIso(),
    updatedAt: nowIso(),
  },
  {
    id: "u_2087",
    fullName: "Mariam Adel",
    email: "mariam@academiq.local",
    role: "student",
    moodleUserId: "55087",
    studentId: "S20210087",
    createdAt: nowIso(),
    updatedAt: nowIso(),
  },
  {
    id: "u_3301",
    fullName: "Omar Saleh",
    email: "omar@academiq.local",
    role: "student",
    moodleUserId: "55133",
    studentId: "S20200133",
    createdAt: nowIso(),
    updatedAt: nowIso(),
  },
];

let mockIdCounter = 1000;

/** Mock sign-in: admins are any user whose stored role is "admin". */
export function getMockAuthUser(email: string): AuthUser {
  const normalized = email.trim().toLowerCase();
  const match = mockUsers.find((u) => u.email.toLowerCase() === normalized);
  if (match) return match;
  // Unknown emails resolve to a default student so the demo flow still works.
  return {
    id: "u_guest",
    fullName: email.split("@")[0] || "Student",
    email: normalized,
    role: "student",
    moodleUserId: null,
    studentId: null,
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
}

export function getMockUsers(search?: string): AuthUser[] {
  if (!search) return [...mockUsers];
  const q = search.trim().toLowerCase();
  return mockUsers.filter((u) =>
    [u.fullName, u.email, u.studentId ?? "", u.moodleUserId ?? ""]
      .join(" ")
      .toLowerCase()
      .includes(q),
  );
}

export function createMockUser(input: UserInput): {
  user: AuthUser;
  generatedPassword?: string;
} {
  const user: AuthUser = {
    id: `u_${(mockIdCounter += 1)}`,
    fullName: input.fullName,
    email: input.email.trim().toLowerCase(),
    role: input.role,
    moodleUserId: input.moodleUserId ?? null,
    studentId: input.studentId ?? null,
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
  mockUsers = [user, ...mockUsers];
  return {
    user,
    generatedPassword: input.password ? undefined : "Mock@Pass1234",
  };
}

export function updateMockUser(
  id: string,
  input: Partial<UserInput>,
): AuthUser {
  mockUsers = mockUsers.map((u) =>
    u.id === id
      ? {
          ...u,
          fullName: input.fullName ?? u.fullName,
          email: input.email?.trim().toLowerCase() ?? u.email,
          role: (input.role as Role) ?? u.role,
          moodleUserId:
            input.moodleUserId !== undefined ? input.moodleUserId : u.moodleUserId,
          studentId: input.studentId !== undefined ? input.studentId : u.studentId,
          updatedAt: nowIso(),
        }
      : u,
  );
  return mockUsers.find((u) => u.id === id)!;
}

export function deleteMockUser(id: string): void {
  mockUsers = mockUsers.filter((u) => u.id !== id);
}

export function resetMockPassword(): string {
  return "Mock@Reset1234";
}

export const mockCourses: Course[] = [
  { id: "c_cs204", name: "Data Structures & Algorithms", code: "CS204" },
  { id: "c_cs311", name: "Operating Systems", code: "CS311" },
  { id: "c_math210", name: "Linear Algebra", code: "MATH210" },
  { id: "c_se340", name: "Software Engineering", code: "SE340" },
];

export const mockDashboard: DashboardData = {
  student: mockStudent,
  stats: {
    averageScore: 78.4,
    averageCompletion: 84,
    enrolledCourses: mockCourses.length,
  },
  studyTime: [
    { label: "Week of May 12", hours: 9.5 },
    { label: "Week of May 19", hours: 12.0 },
    { label: "Week of May 26", hours: 14.5 },
  ],
  burnout: {
    level: "Low Risk",
    message:
      "Your overall workload is manageable, but study time has been climbing for three weeks straight. Keep an eye on rest and pacing.",
  },
};

const performanceByCourse: Record<string, PerformanceAnalysis> = {
  c_cs204: {
    course: mockCourses[0],
    predictedGrade: 82,
    status: "Good",
    courseAverage: 79.5,
    hasGradeData: true,
    engine: "ml",
    mlAvailable: true,
    activityDataSource: "synced",
    activityStatsNote:
      "Activity stats below are based on your latest synced Moodle activity records.",
    statistics: {
      quizzes: { attempted: 5, total: 6, averageScore: 81 },
      assignments: { attempted: 4, total: 5, averageScore: 77 },
      totalTimeHours: 41.5,
      weeklyAverageHours: 3.8,
      weeklyAverageEstimated: false,
    },
  },
  c_cs311: {
    course: mockCourses[1],
    predictedGrade: 64,
    status: "At Risk",
    courseAverage: 61.2,
    hasGradeData: true,
    engine: "ml",
    mlAvailable: true,
    activityDataSource: "synced",
    activityStatsNote:
      "Activity stats below are based on your latest synced Moodle activity records.",
    statistics: {
      quizzes: { attempted: 3, total: 6, averageScore: 58 },
      assignments: { attempted: 2, total: 5, averageScore: 63 },
      totalTimeHours: 18.0,
      weeklyAverageHours: 1.6,
      weeklyAverageEstimated: false,
    },
  },
  c_math210: {
    course: mockCourses[2],
    predictedGrade: 73,
    status: "Average",
    courseAverage: 71.0,
    hasGradeData: true,
    engine: "ml",
    mlAvailable: true,
    activityDataSource: "synced",
    activityStatsNote:
      "Activity stats below are based on your latest synced Moodle activity records.",
    statistics: {
      quizzes: { attempted: 6, total: 7, averageScore: 70 },
      assignments: { attempted: 3, total: 4, averageScore: 74 },
      totalTimeHours: 28.5,
      weeklyAverageHours: 2.6,
      weeklyAverageEstimated: false,
    },
  },
  c_se340: {
    course: mockCourses[3],
    predictedGrade: 88,
    status: "Good",
    courseAverage: 86.3,
    hasGradeData: true,
    engine: "ml",
    mlAvailable: true,
    activityDataSource: "synced",
    activityStatsNote:
      "Activity stats below are based on your latest synced Moodle activity records.",
    statistics: {
      quizzes: { attempted: 4, total: 4, averageScore: 90 },
      assignments: { attempted: 5, total: 5, averageScore: 85 },
      totalTimeHours: 36.0,
      weeklyAverageHours: 3.3,
      weeklyAverageEstimated: false,
    },
  },
};

const insightsByCourse: Record<string, CourseInsights> = {
  c_cs204: {
    course: mockCourses[0],
    isHighPerformer: true,
    classificationSummary:
      "You are currently classified as a high performer in this course. Your engagement and quiz scores are above the class trend.",
    riskFactors: [
      {
        title: "Slipping assignment scores",
        description:
          "Your last two assignment scores dipped below your course average. Revisiting feedback before the next submission would protect your predicted grade.",
        impact: 42,
        feature: "material_clicks",
        recommendation: recommendationFor("material_clicks"),
      },
      {
        title: "One missed quiz",
        description:
          "You have one unattempted quiz remaining. Attempting it adds a reliable data point and lifts your completion rate.",
        impact: 28,
        feature: "quiz_attempts",
        recommendation: recommendationFor("quiz_attempts"),
      },
    ],
  },
  c_cs311: {
    course: mockCourses[1],
    isHighPerformer: false,
    classificationSummary:
      "You are not currently a high performer in this course. The model flags this course as your highest-risk enrolment this term.",
    riskFactors: [
      {
        title: "Low weekly engagement",
        description:
          "Weekly study time on this course (1.6h) is less than half your average across other courses. Engagement in weeks 4-6 was especially low.",
        impact: 71,
        feature: "access_frequency",
        recommendation: recommendationFor("access_frequency"),
      },
      {
        title: "Missed assignments",
        description:
          "Three of five assignments are unattempted. Missing graded work is the single largest drag on your predicted grade here.",
        impact: 64,
        feature: "assignment_submissions",
        recommendation: recommendationFor("assignment_submissions"),
      },
      {
        title: "Declining quiz scores",
        description:
          "Quiz scores trended downward across your last three attempts, suggesting topics are not being consolidated.",
        impact: 49,
        feature: "quiz_attempts",
        recommendation: recommendationFor("quiz_attempts"),
      },
    ],
  },
  c_math210: {
    course: mockCourses[2],
    isHighPerformer: false,
    classificationSummary:
      "You are classified as an average performer in this course. A modest, focused increase in study time would likely move you into the high-performer band.",
    riskFactors: [
      {
        title: "Inconsistent study cadence",
        description:
          "Study sessions are clustered right before deadlines rather than spread across the week, which the model links to lower retention.",
        impact: 38,
        feature: "engagement_consistency",
        recommendation: recommendationFor("engagement_consistency"),
      },
      {
        title: "One overdue assignment",
        description:
          "One assignment remains unattempted. Submitting it would both raise your average and improve your engagement signal.",
        impact: 31,
        feature: "assignment_submissions",
        recommendation: recommendationFor("assignment_submissions"),
      },
    ],
  },
  c_se340: {
    course: mockCourses[3],
    isHighPerformer: true,
    classificationSummary:
      "You are a high performer in this course with full task completion and strong, stable quiz scores. No significant risk factors detected.",
    riskFactors: [
      {
        title: "Plateauing study time",
        description:
          "Weekly study time has been flat. Maintaining it is fine given your strong scores, but there is little buffer if the workload increases.",
        impact: 18,
        feature: "total_time_spent",
        recommendation: recommendationFor("total_time_spent"),
      },
    ],
  },
};

const materialsByCourse: Record<string, LearningMaterial[]> = {
  c_cs204: [
    { id: "m_204_1", title: "Lecture 1 — Arrays & Complexity", kind: "Slides" },
    { id: "m_204_2", title: "Lecture 2 — Linked Lists", kind: "Slides" },
    { id: "m_204_3", title: "Lecture 3 — Stacks & Queues", kind: "PDF" },
    { id: "m_204_4", title: "Lecture 4 — Trees & Traversals", kind: "PDF" },
    { id: "m_204_5", title: "Tutorial Notes — Big-O Practice", kind: "Notes" },
  ],
  c_cs311: [
    { id: "m_311_1", title: "Processes & Threads", kind: "Slides" },
    { id: "m_311_2", title: "CPU Scheduling", kind: "Slides" },
    { id: "m_311_3", title: "Memory Management", kind: "PDF" },
    { id: "m_311_4", title: "Deadlocks", kind: "PDF" },
  ],
  c_math210: [
    { id: "m_210_1", title: "Vectors & Spaces", kind: "Slides" },
    { id: "m_210_2", title: "Matrices & Determinants", kind: "PDF" },
    { id: "m_210_3", title: "Eigenvalues & Eigenvectors", kind: "PDF" },
  ],
  c_se340: [
    { id: "m_340_1", title: "Requirements Engineering", kind: "Slides" },
    { id: "m_340_2", title: "Design Patterns", kind: "PDF" },
    { id: "m_340_3", title: "Testing Strategies", kind: "Notes" },
  ],
};

export function getMockPerformance(courseId: string): PerformanceAnalysis {
  return performanceByCourse[courseId] ?? performanceByCourse.c_cs204;
}

export function getMockInsights(courseId: string): CourseInsights {
  return insightsByCourse[courseId] ?? insightsByCourse.c_cs204;
}

export function getMockMaterials(courseId: string): LearningMaterial[] {
  return materialsByCourse[courseId] ?? [];
}

export function getMockQuiz(
  courseId: string,
  materialIds: string[],
): GeneratedQuiz {
  return {
    courseId,
    materialIds,
    questions: [
      {
        id: "q1",
        question:
          "Which data structure offers O(1) average-case insertion and lookup by key?",
        options: ["Array", "Hash table", "Binary search tree", "Linked list"],
        correctIndex: 1,
      },
      {
        id: "q2",
        question:
          "What is the worst-case time complexity of searching an unsorted array of n elements?",
        options: ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
        correctIndex: 2,
      },
      {
        id: "q3",
        question: "A stack follows which ordering principle?",
        options: [
          "First In, First Out",
          "Last In, First Out",
          "Priority order",
          "Random access",
        ],
        correctIndex: 1,
      },
    ],
  };
}
