import { Link } from "react-router-dom";
import { motion } from "motion/react";
import Header from "@/components/layout/Header";
import Footer from "@/components/layout/Footer";
import HeroSection from "@/components/home/HeroSection";
import {
  BookMarked, TrendingUp, AlertTriangle, Cpu,
  ChevronRight,
} from "lucide-react";

// ── Feature entry ──────────────────────────────────────────────────────────────
const features = [
  {
    number: "01",
    icon: BookMarked,
    title: "Course Overview",
    body: "Every enrolled course, completion status, and activity timeline — one unified view, no tab-switching.",
  },
  {
    number: "02",
    icon: TrendingUp,
    title: "Performance Analytics",
    body: "Quiz trends, assignment scores, and final grade predictions rendered with precision charts and animated counters.",
  },
  {
    number: "03",
    icon: AlertTriangle,
    title: "Risk Detection",
    body: "Early-warning ML classifier surfaces at-risk patterns before they compound — not after exams.",
  },
  {
    number: "04",
    icon: Cpu,
    title: "Moodle Intelligence",
    body: "Your Chrome Extension pushes activity data to the backend; models run automatically. Zero manual input.",
  },
];

// ── Component ──────────────────────────────────────────────────────────────────
const Index = () => {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Header />

      <main className="flex-1">
        <HeroSection />

        {/* ── Features section ─────────────────────────────────────────── */}
        <section className="relative py-24">
          {/* Background grid overlay */}
          <div className="pointer-events-none absolute inset-0 bg-grid opacity-20" />

          <div className="container relative">
            {/* Section header — left aligned */}
            <div className="mb-14 max-w-xl">
              <motion.p
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5 }}
                className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary"
              >
                Built for students
              </motion.p>
              <motion.h2
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.06, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                className="text-3xl font-bold tracking-tight text-foreground md:text-4xl"
              >
                Everything you need
                <br />
                to stay ahead.
              </motion.h2>
            </div>

            {/* Feature list — NOT a uniform grid */}
            <div className="space-y-px">
              {features.map(({ number, icon: Icon, title, body }, i) => (
                <motion.div
                  key={number}
                  initial={{ opacity: 0, x: -16 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{
                    delay: 0.05 + i * 0.08,
                    duration: 0.5,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="group flex items-start gap-6 rounded-xl border border-transparent px-5 py-5
                    transition-all hover:border-border/60 hover:bg-card/50"
                >
                  {/* Number */}
                  <span className="shrink-0 text-xs font-bold tabular text-muted-foreground/40 pt-0.5 w-5">
                    {number}
                  </span>

                  {/* Icon */}
                  <div className="shrink-0 flex h-9 w-9 items-center justify-center rounded-lg
                    bg-primary/10 ring-1 ring-primary/20 transition-all group-hover:ring-primary/40">
                    <Icon className="h-4 w-4 text-primary" />
                  </div>

                  {/* Copy */}
                  <div className="flex-1 min-w-0">
                    <h3 className="mb-1 text-sm font-semibold text-foreground">{title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{body}</p>
                  </div>

                  {/* Arrow — appears on hover */}
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/30 mt-0.5
                    transition-all group-hover:translate-x-0.5 group-hover:text-primary" />
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Final CTA strip ───────────────────────────────────────────── */}
        <section className="relative border-t border-border/40 py-16">
          <div className="pointer-events-none absolute inset-0 bg-spotlight opacity-50" />
          <div className="container relative text-center">
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-primary"
            >
              Ready to start?
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.08, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
              className="mb-6 text-2xl font-bold tracking-tight text-foreground"
            >
              Sign in with your university credentials.
            </motion.h2>
            <motion.div
              whileTap={{ scale: 0.97 }}
              className="inline-block"
            >
              <Link
                to="/signin"
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm
                  font-semibold text-primary-foreground transition-all hover:bg-primary/90 glow-primary"
              >
                Access Dashboard
                <ChevronRight className="h-4 w-4" />
              </Link>
            </motion.div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
};

export default Index;
