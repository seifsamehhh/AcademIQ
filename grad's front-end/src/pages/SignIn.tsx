import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { motion } from "motion/react";
import { useUser } from "@/context/UserContext";
import { useABTest } from "@/hooks/useABTest";
import { apiPost } from "@/lib/apiClient";
import type { LoginResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GraduationCap, Loader2, Zap, BarChart3, Brain } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// ── Animated feature pill ──────────────────────────────────────────────────────
const Pill = ({ icon: Icon, text, delay }: { icon: typeof Zap; text: string; delay: number }) => (
  <motion.div
    initial={{ opacity: 0, x: -16 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ delay, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    className="flex items-center gap-2.5 rounded-full border border-primary/20 bg-primary/5 px-4 py-2 text-sm text-muted-foreground"
  >
    <Icon className="h-3.5 w-3.5 text-primary" />
    {text}
  </motion.div>
);

// ── Component ──────────────────────────────────────────────────────────────────
const SignIn = () => {
  const navigate  = useNavigate();
  const location  = useLocation();
  const { setUsername, setLoginData } = useUser();
  const { toast } = useToast();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/dashboard";

  const { isVariantA: ctaVariantA } = useABTest("signin_cta");
  const ctaText = ctaVariantA ? "Access Dashboard" : "Sign In";

  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData]   = useState({ username: "", password: "" });
  const [errors, setErrors]       = useState({ username: "", password: "", general: "" });

  const validateForm = (): boolean => {
    const next = { username: "", password: "", general: "" };
    let ok = true;
    if (!formData.username.trim()) { next.username = "Username is required"; ok = false; }
    else if (formData.username.trim().length < 3) { next.username = "At least 3 characters"; ok = false; }
    if (!formData.password) { next.password = "Password is required"; ok = false; }
    else if (formData.password.length < 6) { next.password = "At least 6 characters"; ok = false; }
    setErrors(next);
    return ok;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsLoading(true);
    setErrors({ username: "", password: "", general: "" });

    try {
      const data = await apiPost<LoginResponse>("/api/auth/login", {
        username: formData.username,
        password: formData.password,
      });
      setLoginData(data.username, data.token, data.student_id);
    } catch {
      setUsername(formData.username.trim());
    }

    toast({ title: "Welcome back!", description: "Signed in successfully." });
    navigate(from, { replace: true });
    setIsLoading(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name as keyof typeof errors]) {
      setErrors(prev => ({ ...prev, [name]: "" }));
    }
  };

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-background">

      {/* ── Background: grid + spotlight ─────────────────────────────── */}
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-50" />
      <div className="pointer-events-none absolute inset-0 bg-spotlight" />

      {/* ── Left panel — brand statement ─────────────────────────────── */}
      <div className="relative hidden lg:flex lg:w-1/2 lg:flex-col lg:justify-between lg:p-12">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 w-fit">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/30"
          >
            <GraduationCap className="h-5 w-5 text-primary" />
          </motion.div>
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1, duration: 0.5 }}
            className="text-xl font-bold text-foreground"
          >
            AcademIQ
          </motion.span>
        </Link>

        {/* Main statement */}
        <div className="space-y-8">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
              Academic Intelligence
            </p>
            <h1 className="text-5xl font-bold leading-[1.1] tracking-tight text-foreground">
              Know your grades
              <br />
              <span className="text-primary">before</span> they happen.
            </h1>
            <p className="mt-5 max-w-sm text-base text-muted-foreground leading-relaxed">
              ML-powered insights from your Moodle data. Predict performance,
              spot burnout risk, and act before it's too late.
            </p>
          </motion.div>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2.5">
            <Pill icon={Brain}     text="AI Classification"      delay={0.4} />
            <Pill icon={BarChart3} text="Predicted Grades"       delay={0.5} />
            <Pill icon={Zap}       text="Live Moodle Sync"       delay={0.6} />
          </div>
        </div>

        {/* Bottom quote */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.6 }}
          className="text-xs text-muted-foreground/60"
        >
          Data stays local. Predictions are yours.
        </motion.p>
      </div>

      {/* ── Right panel — form ────────────────────────────────────────── */}
      <div className="relative flex w-full items-center justify-center px-6 py-12 lg:w-1/2">
        {/* Vertical divider */}
        <div className="absolute left-0 top-1/2 hidden h-[60%] -translate-y-1/2 w-px bg-gradient-to-b from-transparent via-border to-transparent lg:block" />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo */}
          <Link to="/" className="mb-10 flex items-center gap-2.5 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/30">
              <GraduationCap className="h-4.5 w-4.5 text-primary" />
            </div>
            <span className="text-lg font-bold text-foreground">AcademIQ</span>
          </Link>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-foreground">Sign in</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Access your intelligence dashboard
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {errors.general && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              >
                {errors.general}
              </motion.div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="username" className="text-sm font-medium text-foreground/80">
                Username
              </Label>
              <Input
                id="username"
                name="username"
                type="text"
                value={formData.username}
                onChange={handleChange}
                placeholder="Enter your username"
                className={`h-11 bg-input/50 border-border/60 placeholder:text-muted-foreground/40
                  focus-visible:border-primary/60 focus-visible:ring-1 focus-visible:ring-primary/30
                  transition-all duration-200
                  ${errors.username ? "border-destructive/60 focus-visible:ring-destructive/30" : ""}`}
                disabled={isLoading}
                autoComplete="username"
              />
              {errors.username && (
                <p className="text-xs text-destructive">{errors.username}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium text-foreground/80">
                Password
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="Enter your password"
                className={`h-11 bg-input/50 border-border/60 placeholder:text-muted-foreground/40
                  focus-visible:border-primary/60 focus-visible:ring-1 focus-visible:ring-primary/30
                  transition-all duration-200
                  ${errors.password ? "border-destructive/60 focus-visible:ring-destructive/30" : ""}`}
                disabled={isLoading}
                autoComplete="current-password"
              />
              {errors.password && (
                <p className="text-xs text-destructive">{errors.password}</p>
              )}
            </div>

            <motion.div whileTap={{ scale: 0.98 }}>
              <Button
                type="submit"
                className="h-11 w-full bg-primary text-sm font-semibold text-primary-foreground
                  hover:bg-primary/90 glow-primary-sm transition-all duration-200"
                disabled={isLoading}
              >
                {isLoading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Signing in…</>
                ) : ctaText}
              </Button>
            </motion.div>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground/60">
            Use any username (3+ chars) and password (6+ chars) to sign in.
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default SignIn;
