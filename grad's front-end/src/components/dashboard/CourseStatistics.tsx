import { FileText, HelpCircle, Clock } from "lucide-react";
import { motion } from "motion/react";
import { CourseStats } from "@/data/mockData";
import { cn } from "@/lib/utils";

interface CourseStatisticsProps {
  stats: CourseStats;
}

interface StatBlockProps {
  icon: typeof FileText;
  label: string;
  rows: { key: string; value: string }[];
  delay: number;
  color?: string;
}

const StatBlock = ({ icon: Icon, label, rows, delay, color = "text-primary" }: StatBlockProps) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    className="rounded-xl border border-border/40 bg-muted/20 p-4"
  >
    <div className="mb-3 flex items-center gap-2.5">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
        <Icon className={cn("h-4 w-4", color)} />
      </div>
      <span className="text-sm font-semibold text-foreground">{label}</span>
    </div>
    <div className="space-y-1.5">
      {rows.map(({ key, value }) => (
        <div key={key} className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{key}</span>
          <span className="font-semibold tabular text-foreground">{value}</span>
        </div>
      ))}
    </div>
  </motion.div>
);

const CourseStatistics = ({ stats }: CourseStatisticsProps) => (
  <div className="rounded-xl border border-border/50 bg-card/50 p-5 backdrop-blur-sm">
    <p className="mb-5 text-sm font-semibold text-foreground">Course Statistics</p>

    <div className="grid gap-3 sm:grid-cols-3">
      <StatBlock
        icon={FileText}
        label="Assignments"
        delay={0}
        rows={[
          { key: "Submitted", value: `${stats.submittedAssignments} / ${stats.totalAssignments}` },
          { key: "Avg grade",  value: `${stats.avgAssignmentGrade}%` },
        ]}
      />
      <StatBlock
        icon={HelpCircle}
        label="Quizzes"
        delay={0.05}
        rows={[
          { key: "Completed", value: `${stats.completedQuizzes} / ${stats.totalQuizzes}` },
          { key: "Avg grade", value: `${stats.avgQuizGrade}%` },
        ]}
      />
      <StatBlock
        icon={Clock}
        label="Time Spent"
        delay={0.1}
        rows={[
          { key: "Total",      value: `${stats.timeSpentHours}h` },
          { key: "Weekly avg", value: `${(stats.timeSpentHours / 6).toFixed(1)}h` },
        ]}
      />
    </div>
  </div>
);

export default CourseStatistics;
