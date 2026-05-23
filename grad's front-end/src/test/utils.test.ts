/**
 * utils.test.ts — Unit tests for mockData utility functions.
 *
 * Tests: getOverallStatus, getCourseStatus, getPredictedStatus
 * All are pure functions — no DOM, no React, no mocking needed.
 *
 * Run: npm test
 */

import { describe, it, expect } from "vitest";
import {
  getOverallStatus,
  getCourseStatus,
  getPredictedStatus,
} from "@/data/mockData";

// ═══════════════════════════════════════════════════════════════
// getOverallStatus
// Thresholds: <70 → "At Risk", 70–84 → "Good", ≥85 → "Perfect"
// ═══════════════════════════════════════════════════════════════
describe("getOverallStatus", () => {
  // ── At Risk band ──────────────────────────────────────────
  it('returns "At Risk" for score 0', () => {
    expect(getOverallStatus(0)).toBe("At Risk");
  });

  it('returns "At Risk" for score 50', () => {
    expect(getOverallStatus(50)).toBe("At Risk");
  });

  it('returns "At Risk" for score 69', () => {
    expect(getOverallStatus(69)).toBe("At Risk");
  });

  it('returns "At Risk" for score 69.99', () => {
    expect(getOverallStatus(69.99)).toBe("At Risk");
  });

  // ── Boundary: 70 is the first "Good" value ───────────────
  it('returns "Good" for score exactly 70 (boundary)', () => {
    expect(getOverallStatus(70)).toBe("Good");
  });

  it('returns "Good" for score 77', () => {
    expect(getOverallStatus(77)).toBe("Good");
  });

  it('returns "Good" for score 84', () => {
    expect(getOverallStatus(84)).toBe("Good");
  });

  it('returns "Good" for score 84.99', () => {
    expect(getOverallStatus(84.99)).toBe("Good");
  });

  // ── Boundary: 85 is the first "Perfect" value ────────────
  it('returns "Perfect" for score exactly 85 (boundary)', () => {
    expect(getOverallStatus(85)).toBe("Perfect");
  });

  it('returns "Perfect" for score 92', () => {
    expect(getOverallStatus(92)).toBe("Perfect");
  });

  it('returns "Perfect" for score 100', () => {
    expect(getOverallStatus(100)).toBe("Perfect");
  });
});

// ═══════════════════════════════════════════════════════════════
// getCourseStatus
// Thresholds: <70 → "Bad", 70–84 → "Average", ≥85 → "Good"
// ═══════════════════════════════════════════════════════════════
describe("getCourseStatus", () => {
  it('returns "Bad" for score 0', () => {
    expect(getCourseStatus(0)).toBe("Bad");
  });

  it('returns "Bad" for score 65', () => {
    expect(getCourseStatus(65)).toBe("Bad");
  });

  it('returns "Bad" for score 69.99', () => {
    expect(getCourseStatus(69.99)).toBe("Bad");
  });

  it('returns "Average" for score 70 (boundary)', () => {
    expect(getCourseStatus(70)).toBe("Average");
  });

  it('returns "Average" for score 78', () => {
    expect(getCourseStatus(78)).toBe("Average");
  });

  it('returns "Average" for score 84.99', () => {
    expect(getCourseStatus(84.99)).toBe("Average");
  });

  it('returns "Good" for score 85 (boundary)', () => {
    expect(getCourseStatus(85)).toBe("Good");
  });

  it('returns "Good" for score 100', () => {
    expect(getCourseStatus(100)).toBe("Good");
  });
});

// ═══════════════════════════════════════════════════════════════
// getPredictedStatus
// Thresholds: <65 → "At Risk", 65–74 → "Average",
//             75–84 → "Good", ≥85 → "Excellent"
// ═══════════════════════════════════════════════════════════════
describe("getPredictedStatus", () => {
  it('returns "At Risk" for score 0', () => {
    expect(getPredictedStatus(0)).toBe("At Risk");
  });

  it('returns "At Risk" for score 50', () => {
    expect(getPredictedStatus(50)).toBe("At Risk");
  });

  it('returns "At Risk" for score 64', () => {
    expect(getPredictedStatus(64)).toBe("At Risk");
  });

  it('returns "At Risk" for score 64.99', () => {
    expect(getPredictedStatus(64.99)).toBe("At Risk");
  });

  it('returns "Average" for score 65 (boundary)', () => {
    expect(getPredictedStatus(65)).toBe("Average");
  });

  it('returns "Average" for score 70', () => {
    expect(getPredictedStatus(70)).toBe("Average");
  });

  it('returns "Average" for score 74', () => {
    expect(getPredictedStatus(74)).toBe("Average");
  });

  it('returns "Average" for score 74.99', () => {
    expect(getPredictedStatus(74.99)).toBe("Average");
  });

  it('returns "Good" for score 75 (boundary)', () => {
    expect(getPredictedStatus(75)).toBe("Good");
  });

  it('returns "Good" for score 80', () => {
    expect(getPredictedStatus(80)).toBe("Good");
  });

  it('returns "Good" for score 84.99', () => {
    expect(getPredictedStatus(84.99)).toBe("Good");
  });

  it('returns "Excellent" for score 85 (boundary)', () => {
    expect(getPredictedStatus(85)).toBe("Excellent");
  });

  it('returns "Excellent" for score 95', () => {
    expect(getPredictedStatus(95)).toBe("Excellent");
  });

  it('returns "Excellent" for score 100', () => {
    expect(getPredictedStatus(100)).toBe("Excellent");
  });
});
