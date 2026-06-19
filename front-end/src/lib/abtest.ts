/**
 * Lightweight A/B test assignment for UI experiments (no external service).
 */

const STORAGE_PREFIX = "academiq_ab_";

export function getABVariant(testName: string): "A" | "B" {
  if (typeof window === "undefined") return "A";
  const key = `${STORAGE_PREFIX}${testName}`;
  try {
    const stored = window.localStorage.getItem(key);
    if (stored === "A" || stored === "B") return stored;
    const variant: "A" | "B" = Math.random() < 0.5 ? "A" : "B";
    window.localStorage.setItem(key, variant);
    return variant;
  } catch {
    return "A";
  }
}

export function isVariantA(testName: string): boolean {
  return getABVariant(testName) === "A";
}
