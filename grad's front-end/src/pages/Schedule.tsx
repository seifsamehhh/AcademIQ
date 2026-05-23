import { motion } from "motion/react";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import Footer from "@/components/layout/Footer";
import { useUser } from "@/context/UserContext";
import { scheduleData } from "@/data/mockData";
import { Clock, MapPin, CalendarDays } from "lucide-react";
import { cn } from "@/lib/utils";

const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"];

// Day accent colours — subtle, not garish
const dayColors: Record<string, { badge: string; dot: string }> = {
  Sunday:    { badge: "bg-sky-500/10 text-sky-400 ring-sky-500/20",     dot: "bg-sky-400"     },
  Monday:    { badge: "bg-violet-500/10 text-violet-400 ring-violet-500/20", dot: "bg-violet-400" },
  Tuesday:   { badge: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20", dot: "bg-emerald-400" },
  Wednesday: { badge: "bg-amber-500/10 text-amber-400 ring-amber-500/20",  dot: "bg-amber-400"  },
  Thursday:  { badge: "bg-rose-500/10 text-rose-400 ring-rose-500/20",    dot: "bg-rose-400"   },
};

// ── Component ──────────────────────────────────────────────────────────────────
const Schedule = () => {
  const { username } = useUser();

  // Flatten to a sorted list of { day, ...entry } objects
  const rows = days.flatMap((day) =>
    scheduleData
      .filter((e) => e.day === day)
      .map((e) => ({ day, ...e }))
  );

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Spotlight */}
      <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-50" />

      <DashboardHeader username={username || "Student"} />

      <main className="container relative flex-1 py-8">
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8"
        >
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Weekly Timetable
          </p>
          <div className="flex items-center gap-3">
            <CalendarDays className="h-6 w-6 text-muted-foreground" />
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Schedule</h1>
          </div>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Your class timetable for the current semester.
          </p>
        </motion.div>

        {/* Schedule card */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="overflow-hidden rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm"
        >
          {/* Column headers */}
          <div className="grid grid-cols-12 gap-0 border-b border-border/40 px-5 py-3">
            <span className="col-span-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              Day
            </span>
            <span className="col-span-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              Time
            </span>
            <span className="col-span-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              Course
            </span>
            <span className="col-span-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              Room
            </span>
          </div>

          {/* Rows */}
          <div className="divide-y divide-border/30">
            {rows.map((row, i) => {
              const colors = dayColors[row.day] ?? dayColors["Monday"];
              return (
                <motion.div
                  key={`${row.day}-${row.time}-${i}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    delay: 0.15 + i * 0.04,
                    duration: 0.4,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="group grid grid-cols-12 items-center gap-0 px-5 py-4
                    transition-colors hover:bg-muted/20"
                >
                  {/* Day badge */}
                  <div className="col-span-3 flex items-center gap-2">
                    <span className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1",
                      colors.badge
                    )}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", colors.dot)} />
                      {row.day}
                    </span>
                  </div>

                  {/* Time */}
                  <div className="col-span-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3 shrink-0" />
                    <span className="tabular">{row.time}</span>
                  </div>

                  {/* Course */}
                  <div className="col-span-4 min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">{row.courseCode}</p>
                    <p className="truncate text-xs text-muted-foreground">{row.courseName}</p>
                  </div>

                  {/* Room */}
                  <div className="col-span-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3 shrink-0" />
                    {row.room}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </main>

      <Footer />
    </div>
  );
};

export default Schedule;
