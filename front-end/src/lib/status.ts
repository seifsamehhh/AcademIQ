import type { BadgeProps } from "@/components/ui/badge";
import type { BurnoutLevel, PerformanceStatus } from "./types";

type BadgeVariant = NonNullable<BadgeProps["variant"]>;

/** Map a burnout level to a badge variant + the bar/accent color it uses. */
export function burnoutStyle(level: BurnoutLevel): {
  variant: BadgeVariant;
  /** Tailwind text color class for emphasis. */
  text: string;
  /** Tailwind bg color class for solid accents. */
  bg: string;
} {
  switch (level) {
    case "Safe":
      return { variant: "success", text: "text-success", bg: "bg-success" };
    case "Low Risk":
      return { variant: "default", text: "text-primary", bg: "bg-primary" };
    case "Medium Risk":
      return { variant: "warning", text: "text-warning", bg: "bg-warning" };
    case "High Risk":
      return {
        variant: "destructive",
        text: "text-destructive",
        bg: "bg-destructive",
      };
  }
}

/** Map a clustering status to a badge variant + accent color. */
export function performanceStyle(status: PerformanceStatus): {
  variant: BadgeVariant;
  text: string;
} {
  switch (status) {
    case "Good":
    case "On Track":
      return { variant: "success", text: "text-success" };
    case "Average":
    case "Room to improve":
      return { variant: "warning", text: "text-warning" };
    case "At Risk":
      return { variant: "destructive", text: "text-destructive" };
  }
}
