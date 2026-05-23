/**
 * useABTest — React hook for accessing A/B test variants.
 *
 * Usage:
 *   const { variant, isControl, isVariantA } = useABTest("signin_cta");
 *
 * The hook reports exposure once on mount and returns the sticky variant.
 */

import { useEffect, useRef } from "react";
import { getVariant, trackExposure, type Variant } from "@/lib/abtest";

interface ABTestResult {
  variant: Variant;
  isControl: boolean;
  isVariantA: boolean;
}

export function useABTest(experimentName: string): ABTestResult {
  const variant = getVariant(experimentName);
  const exposureReported = useRef(false);

  useEffect(() => {
    if (!exposureReported.current) {
      trackExposure(experimentName, variant);
      exposureReported.current = true;
    }
  }, [experimentName, variant]);

  return {
    variant,
    isControl:  variant === "control",
    isVariantA: variant === "variant_a",
  };
}
