import { Info } from "lucide-react";
import type { ActivityDataSource } from "@/lib/types";

interface ActivityStatsNoticeProps {
  source: ActivityDataSource;
  note: string;
}

const SOURCE_LABEL: Record<ActivityDataSource, string> = {
  seeded: "Activity source: Moodle activity records",
  synced: "Activity source: synced Moodle activity",
  none: "Activity source: limited activity data",
};

export function ActivityStatsNotice({ source, note }: ActivityStatsNoticeProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border/80 bg-muted/40 p-4 text-sm text-muted-foreground">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
      <div className="space-y-1">
        <p className="font-medium text-foreground">{SOURCE_LABEL[source]}</p>
        <p className="leading-relaxed">{note}</p>
      </div>
    </div>
  );
}
