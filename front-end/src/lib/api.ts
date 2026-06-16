import {
  createMockUser,
  deleteMockUser,
  getMockAuthUser,
  getMockInsights,
  getMockMaterials,
  getMockPerformance,
  getMockQuiz,
  getMockUsers,
  mockCourses,
  mockDashboard,
  resetMockPassword,
  updateMockUser,
} from "./mock";
import type {
  AuthResult,
  AuthUser,
  Course,
  CourseInsights,
  DashboardData,
  GeneratedQuiz,
  LearningMaterial,
  LoginResult,
  PerformanceAnalysis,
  StudentResults,
  UserInput,
  UserMutationResult,
} from "./types";

/**
 * Single seam between the UI and the data layer.
 *
 * Student auth uses JWT access tokens stored in localStorage and sent as
 * Authorization: Bearer headers on protected requests.
 */

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

/** Resolve API base URL from env — no localhost fallback in production builds. */
function getApiBaseUrl(): string {
  if (USE_MOCK) return "";
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set. Copy front-end/.env.example to .env.local.",
    );
  }
  return raw.replace(/\/$/, "");
}

export const ACCESS_TOKEN_KEY = "access_token";
export const STUDENT_ID_KEY = "student_id";
export const STUDENT_NAME_KEY = "student_name";
export const ROLE_KEY = "role";

/** Thrown when the API returns 401/403 so callers can redirect to sign-in. */
export class ApiAuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiAuthError";
    this.status = status;
  }
}

/** Simulate network latency so loading states are exercised in dev. */
function delay<T>(value: T, ms = 400): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredStudentId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STUDENT_ID_KEY);
  } catch {
    return null;
  }
}

export function getStoredStudentName(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STUDENT_NAME_KEY);
  } catch {
    return null;
  }
}

export function getStoredRole(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ROLE_KEY);
  } catch {
    return null;
  }
}

export function persistAuth(data: LoginResult): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
    window.localStorage.setItem(STUDENT_ID_KEY, data.student_id);
    window.localStorage.setItem(STUDENT_NAME_KEY, data.name);
    window.localStorage.setItem(ROLE_KEY, data.role);
  } catch {
    /* ignore */
  }
}

/** Clear all student JWT auth state. */
export function clearAuthStorage(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(STUDENT_ID_KEY);
    window.localStorage.removeItem(STUDENT_NAME_KEY);
    window.localStorage.removeItem(ROLE_KEY);
    window.localStorage.removeItem("academiq.user");
    window.localStorage.removeItem("academiq.token");
  } catch {
    /* ignore */
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const text = await res.text();
    let message = `Request failed (${res.status}): ${path}`;
    try {
      const body = text ? JSON.parse(text) : null;
      if (body?.detail) {
        // detail may be a plain string or a structured object with a "message" key
        const d = body.detail;
        message = typeof d === "object" && d !== null && d.message
          ? String(d.message)
          : String(d);
      }
    } catch {
      if (text) message = text;
    }
    if (res.status === 401 || res.status === 403) {
      throw new ApiAuthError(message, res.status);
    }
    throw new Error(message);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  /* ---------------------------------------------------------------------- */
  /* Student JWT auth                                                       */
  /* ---------------------------------------------------------------------- */

  /** Login with student_id + password → POST /api/auth/login. */
  async login(studentId: string, password: string): Promise<LoginResult> {
    const result = await request<LoginResult>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, password }),
    });
    persistAuth(result);
    return result;
  },

  /** Logout — clears local JWT state (stateless server-side). */
  async logout(): Promise<void> {
    try {
      await request<void>("/api/auth/logout", { method: "POST" });
    } catch {
      /* ignore — token may already be expired */
    } finally {
      clearAuthStorage();
    }
  },

  /** Academic results → GET /student/{student_id}/results (JWT required). */
  async getStudentResults(studentId: string): Promise<StudentResults> {
    return request<StudentResults>(`/student/${studentId}/results`);
  },

  /* ---------------------------------------------------------------------- */
  /* Legacy auth (admin / mock mode)                                        */
  /* ---------------------------------------------------------------------- */

  async signIn(email: string, password: string): Promise<AuthResult> {
    if (USE_MOCK) {
      const user = getMockAuthUser(email);
      return delay({ user, role: user.role, token: "mock-session-token" });
    }
    const result = await request<AuthResult>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ student_id: email, password }),
    });
    return result as unknown as AuthResult;
  },

  async signOut(): Promise<void> {
    if (USE_MOCK) return delay(undefined, 150);
    await api.logout();
  },

  async getMe(): Promise<AuthUser | null> {
    if (USE_MOCK) return delay(null, 150);
    try {
      const data = await request<{
        student_id: string;
        name: string;
        role: string;
      }>("/api/auth/me");
      return {
        id: data.student_id,
        fullName: data.name,
        email: "",
        role: data.role as AuthUser["role"],
        studentId: data.student_id,
      };
    } catch {
      return null;
    }
  },

  /* ---------------------------------------------------------------------- */
  /* Admin — user management (admin role required by the backend)           */
  /* ---------------------------------------------------------------------- */

  async getUsers(search?: string): Promise<AuthUser[]> {
    if (USE_MOCK) return delay(getMockUsers(search));
    const q = search ? `?search=${encodeURIComponent(search)}` : "";
    return request<AuthUser[]>(`/api/admin/users${q}`);
  },

  async createUser(input: UserInput): Promise<UserMutationResult> {
    if (USE_MOCK) return delay(createMockUser(input));
    return request<UserMutationResult>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async updateUser(
    id: string,
    input: Partial<UserInput>,
  ): Promise<UserMutationResult> {
    if (USE_MOCK) return delay({ user: updateMockUser(id, input) });
    return request<UserMutationResult>(`/api/admin/users/${id}`, {
      method: "PUT",
      body: JSON.stringify(input),
    });
  },

  async deleteUser(id: string): Promise<void> {
    if (USE_MOCK) {
      deleteMockUser(id);
      return delay(undefined, 200);
    }
    await request<void>(`/api/admin/users/${id}`, { method: "DELETE" });
  },

  async resetPassword(
    id: string,
    password?: string,
  ): Promise<{ generatedPassword?: string }> {
    if (USE_MOCK) {
      return delay({
        generatedPassword: password ? undefined : resetMockPassword(),
      });
    }
    return request<{ generatedPassword?: string }>(
      `/api/admin/users/${id}/reset-password`,
      { method: "POST", body: JSON.stringify({ password }) },
    );
  },

  /* ---------------------------------------------------------------------- */
  /* Student-facing data                                                    */
  /* ---------------------------------------------------------------------- */

  async getCourses(): Promise<Course[]> {
    if (USE_MOCK) return delay(mockCourses);
    return request<Course[]>("/courses");
  },

  async getDashboard(): Promise<DashboardData> {
    if (USE_MOCK) return delay(mockDashboard);
    return request<DashboardData>("/dashboard");
  },

  async getPerformance(courseId: string): Promise<PerformanceAnalysis> {
    if (USE_MOCK) return delay(getMockPerformance(courseId));
    return request<PerformanceAnalysis>(`/courses/${courseId}/performance`);
  },

  async getInsights(courseId: string): Promise<CourseInsights> {
    if (USE_MOCK) return delay(getMockInsights(courseId));
    return request<CourseInsights>(`/courses/${courseId}/insights`);
  },

  async getMaterials(courseId: string): Promise<LearningMaterial[]> {
    if (USE_MOCK) return delay(getMockMaterials(courseId));
    return request<LearningMaterial[]>(`/courses/${courseId}/materials`);
  },

  async generateQuiz(
    courseId: string,
    materialIds: string[],
  ): Promise<GeneratedQuiz> {
    if (USE_MOCK) return delay(getMockQuiz(courseId, materialIds), 900);
    return request<GeneratedQuiz>(`/courses/${courseId}/quiz`, {
      method: "POST",
      body: JSON.stringify({ materialIds }),
    });
  },
};
