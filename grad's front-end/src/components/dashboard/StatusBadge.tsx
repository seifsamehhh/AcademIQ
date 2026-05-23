import {
  AlertTriangle, CheckCircle2, Trophy,
  TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import { cn } from "@/lib/utils";

type OverallStatus = "At Risk" | "Good" | "Perfect";
type CourseStatus  = "Bad" | "Average" | "Good";

interface StatusBadgeProps {
  status: OverallStatus | CourseStatus;
  type?: "overall" | "course";
}

const StatusBadge = ({ status, type = "overall" }: StatusBadgeProps) => {
  const cfg = (() => {
    if (type === "overall") {
      switch (status) {
        case "At Risk":  return { Icon: AlertTriangle, accent: "destructive",  border: "border-destructive/30 bg-destructive/10",  iconBg: "bg-destructive/15",  text: "text-destructive",  msg: "Your performance needs attention. Reach out to your instructors early." };
        case "Good":     return { Icon: TrendingUp,   accent: "amber",        border: "border-amber-500/30 bg-amber-500/10",       iconBg: "bg-amber-500/15",    text: "text-amber-400",    msg: "Solid progress. Keep pushing toward the top band." };
        case "Perfect":  return { Icon: Trophy,       accent: "emerald",      border: "border-emerald-500/30 bg-emerald-500/10",   iconBg: "bg-emerald-500/15",  text: "text-emerald-400",  msg: "Excellent — you're in the top percentile. Maintain the streak." };
        default:         return { Icon: Minus,        accent: "muted",        border: "border-border/50 bg-muted/20",              iconBg: "bg-muted/30",        text: "text-muted-foreground", msg: "Status unavailable." };
      }
    } else {
      switch (status) {
        case "Bad":     return { Icon: TrendingDown,  accent: "destructive",  border: "border-destructive/30 bg-destructive/10",  iconBg: "bg-destructive/15",  text: "text-destructive",  msg: "Below expectations. Additional help is recommended." };
        case "Average": return { Icon: Minus,         accent: "amber",        border: "border-amber-500/30 bg-amber-500/10",       iconBg: "bg-amber-500/15",    text: "text-amber-400",    msg: "Room to improve. Target consistent quiz preparation." };
        case "Good":    return { Icon: CheckCircle2,  accent: "emerald",      border: "border-emerald-500/30 bg-emerald-500/10",   iconBg: "bg-emerald-500/15",  text: "text-emerald-400",  msg: "Great work in this course!" };
        default:        return { Icon: Minus,         accent: "muted",        border: "border-border/50 bg-muted/20",              iconBg: "bg-muted/30",        text: "text-muted-foreground", msg: "Status unavailable." };
      }
    }
  })();

  return (
    <div className={cn("rounded-xl border p-5 backdrop-blur-sm", cfg.border)}>
      <div className="mb-3 flex items-center gap-3">
        <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg", cfg.iconBg)}>
          <cfg.Icon className={cn("h-4.5 w-4.5", cfg.text)} />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Performance status</p>
          <p className={cn("text-base font-bold", cfg.text)}>{status}</p>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{cfg.msg}</p>
    </div>
  );
};

export default StatusBadge;
