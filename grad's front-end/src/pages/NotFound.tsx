import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "motion/react";
import { GraduationCap } from "lucide-react";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background">
      {/* Background */}
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-30" />
      <div className="pointer-events-none absolute inset-0 bg-spotlight opacity-60" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 text-center"
      >
        {/* Logo mark */}
        <div className="mx-auto mb-8 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/25">
          <GraduationCap className="h-6 w-6 text-primary" />
        </div>

        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">404</p>
        <h1 className="mb-2 text-5xl font-bold tracking-tight text-foreground">Page not found</h1>
        <p className="mb-8 text-sm text-muted-foreground">
          The route{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-foreground">
            {location.pathname}
          </code>{" "}
          doesn't exist.
        </p>

        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm
            font-semibold text-primary-foreground transition-all hover:bg-primary/90 glow-primary-sm"
        >
          Back to home
        </Link>
      </motion.div>
    </div>
  );
};

export default NotFound;
