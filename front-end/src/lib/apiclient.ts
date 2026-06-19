/**
 * API client helpers — wraps the stable `api` module for Mission Control UI code.
 * All requests use the same backend endpoints as the deployed app.
 */

import type { LoginResult } from "./types";
import { getAccessToken } from "./api";

export {
  api,
  ApiAuthError,
  clearAuthStorage,
  getAccessToken,
  getStoredStudentId,
  getStoredStudentName,
} from "./api";

function getApiBaseUrl(): string {
  const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
  if (USE_MOCK) return "";
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set.");
  }
  return raw.replace(/\/$/, "");
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new Error(text || res.statusText || `Request failed (${res.status})`);
  }
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export async function apiGet<T>(path: string): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  return parseJson<T>(res);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseJson<T>(res);
}

export type { LoginResult };
