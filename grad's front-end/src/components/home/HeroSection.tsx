import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowRight, Brain, BarChart3, Zap, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

// ── Animated stat pill ─────────────────────────────────────────────────────────
const Stat = ({ value, label, delay }: { value: string; label: string; delay: number }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    className="flex flex-col"
  >
    <span className="tabular text-2xl font-bold text-foreground">{value}</span>
    <span className="text-xs text-muted-foreground">{label}</span>
  </motion.div>
);

// ── Feature pill ───────────────────────────────────────────────────────────────
const Pill = ({
  icon: Icon, text, delay,
}: { icon: typeof Brain; text: string; delay: number }) => (
  <motion.div
    initial={{ opacity: 0, x: -12 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ delay, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    className="flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5
      px-3.5 py-1.5 text-xs text-muted-foreground"
  >
    <Icon className="h-3 w-3 text-primary" />
    {text}
  </motion.div>
);

// ── Component ──────────────────────────────────────────────────────────────────
const HeroSection = () => {
  return (
    <section className="relative min-h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Background layers */}
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-40" />
      <div className="pointer-events-none absolute inset-0 bg-spotlight" />

      {/* Content — left-aligned, NOT centered */}
      <div className="container relative z-10 flex min-h-[calc(100vh-3.5rem)] flex-col justify-center py-24">
        {/* Overline */}
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-primary"
        >
          Academic Intelligence
        </motion.p>

        {/* Headline — oversized, breaks the grid */}
        <motion.h1
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08, duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
          className="mb-6 max-w-3xl text-5xl font-bold leading-[1.08] tracking-tight text-foreground
            md:text-6xl lg:text-7xl"
        >
          Know your grades
          <br />
          <span className="text-primary">before</span> they happen.
        </motion.h1>

        {/* Sub */}
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8 max-w-lg text-base text-muted-foreground leading-relaxed"
        >
          ML-powered insights from your Moodle data. Predict performance,
          spot burnout risk, and act before it's too late.
        </motion.p>

        {/* Pills */}
        <div className="mb-10 flex flex-wrap gap-2">
          <Pill icon={Brain}     text="AI Classification"  delay={0.28} />
          <Pill icon={BarChart3} text="Predicted Grades"   delay={0.34} />
          <Pill icon={Zap}       text="Live Moodle Sync"   delay={0.40} />
          <Pill icon={Shield}    text="Burnout Detection"  delay={0.46} />
        </div>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.52, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-wrap items-center gap-3"
        >
          <motion.div whileTap={{ scale: 0.97 }}>
            <Button
              asChild
              size="lg"
              className="group h-11 gap-2 bg-primary px-6 text-sm font-semibold
                text-primary-foreground hover:bg-primary/90 glow-primary"
            >
              <Link to="/signin">
                Get Started
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </Button>
          </motion.div>

          <Button
            asChild
            variant="ghost"
            size="lg"
            className="h-11 px-6 text-sm text-muted-foreground hover:text-foreground"
          >
            <Link to="/signin">Sign In</Link>
          </Button>
        </motion.div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.6 }}
          className="mt-16 flex flex-wrap items-center gap-8 border-t border-border/40 pt-8"
        >
          <Stat value="3"   label="ML models"         delay={0.75} />
          <Stat value="10+" label="tracked features"  delay={0.80} />
          <Stat value="4"   label="risk categories"   delay={0.85} />
          <Stat value="∞"   label="Moodle courses"    delay={0.90} />
        </motion.div>
      </div>
    </section>
  );
};

export default HeroSection;
