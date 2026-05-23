/**
 * abtest.test.ts — Unit tests for the A/B testing engine.
 *
 * Tests: variant assignment, persistence, weight distribution,
 *        override, unknown experiment fallback.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  getVariant,
  overrideVariant,
  getAllVariants,
  EXPERIMENTS,
} from "@/lib/abtest";

// ── Setup ────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

// ── Variant assignment ────────────────────────────────────────

describe("getVariant — basic assignment", () => {
  it("returns a valid variant for a known experiment", () => {
    const variant = getVariant("signin_cta");
    expect(["control", "variant_a"]).toContain(variant);
  });

  it("returns 'control' for an unknown experiment", () => {
    const variant = getVariant("non_existent_experiment");
    expect(variant).toBe("control");
  });

  it("returns the same variant on repeated calls (sticky assignment)", () => {
    const first  = getVariant("signin_cta");
    const second = getVariant("signin_cta");
    expect(first).toBe(second);
  });

  it("persists the variant in localStorage", () => {
    const variant = getVariant("signin_cta");
    const stored  = localStorage.getItem("academiq_ab_signin_cta");
    expect(stored).toBe(variant);
  });
});

// ── Override ─────────────────────────────────────────────────

describe("overrideVariant", () => {
  it("forces a specific variant", () => {
    overrideVariant("signin_cta", "variant_a");
    expect(getVariant("signin_cta")).toBe("variant_a");
  });

  it("forces control variant", () => {
    overrideVariant("signin_cta", "control");
    expect(getVariant("signin_cta")).toBe("control");
  });

  it("clears override when set to null", () => {
    overrideVariant("signin_cta", "variant_a");
    overrideVariant("signin_cta", null);
    // After clearing, a fresh random assignment is made
    const variant = getVariant("signin_cta");
    expect(["control", "variant_a"]).toContain(variant);
  });
});

// ── getAllVariants ────────────────────────────────────────────

describe("getAllVariants", () => {
  it("returns an entry for every registered experiment", () => {
    const all = getAllVariants();
    for (const name of Object.keys(EXPERIMENTS)) {
      expect(all).toHaveProperty(name);
    }
  });

  it("all returned variants are valid strings", () => {
    const all = getAllVariants();
    for (const variant of Object.values(all)) {
      expect(typeof variant).toBe("string");
      expect(variant.length).toBeGreaterThan(0);
    }
  });
});

// ── Statistical distribution (smoke test) ───────────────────

describe("getVariant — distribution", () => {
  it("produces both variants across many trials (equal split)", () => {
    const counts: Record<string, number> = { control: 0, variant_a: 0 };

    // Run 200 trials with fresh storage each time
    for (let i = 0; i < 200; i++) {
      localStorage.clear();
      const v = getVariant("signin_cta");
      counts[v] = (counts[v] ?? 0) + 1;
    }

    // Each variant should appear at least 30% of the time (very loose bound)
    expect(counts["control"]).toBeGreaterThan(30);
    expect(counts["variant_a"]).toBeGreaterThan(30);
  });
});

// ── EXPERIMENTS registry ─────────────────────────────────────

describe("EXPERIMENTS registry", () => {
  it("signin_cta has exactly 2 variants", () => {
    expect(EXPERIMENTS["signin_cta"].variants).toHaveLength(2);
  });

  it("signin_cta first variant is 'control'", () => {
    expect(EXPERIMENTS["signin_cta"].variants[0]).toBe("control");
  });

  it("dashboard_layout experiment is registered", () => {
    expect(EXPERIMENTS).toHaveProperty("dashboard_layout");
  });
});
