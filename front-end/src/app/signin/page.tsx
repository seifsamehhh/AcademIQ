"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, GraduationCap, Loader2, Zap, BarChart3, Brain } from "lucide-react";
import { api } from "@/lib/api";
import { isVariantA } from "@/lib/abtest";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({ studentId: "", password: "" });
  const [errors, setErrors] = useState({
    studentId: "",
    password: "",
    general: "",
  });

  const ctaText = isVariantA("signin_cta") ? "Access Dashboard" : "Sign In";

  useEffect(() => {
    if (searchParams.get("expired") === "1") {
      setErrors((prev) => ({
        ...prev,
        general: "Your session has expired. Please sign in again.",
      }));
    }
  }, [searchParams]);

  const validateForm = () => {
    const next = { studentId: "", password: "", general: "" };
    let valid = true;

    if (!formData.studentId.trim()) {
      next.studentId = "Student ID or email is required";
      valid = false;
    }

    if (!formData.password) {
      next.password = "Password is required";
      valid = false;
    }

    setErrors(next);
    return valid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsLoading(true);
    setErrors({ studentId: "", password: "", general: "" });

    try {
      await api.login(formData.studentId.trim(), formData.password);
      router.push("/dashboard");
    } catch (err) {
      setErrors((prev) => ({
        ...prev,
        general: err instanceof Error ? err.message : "Invalid login",
      }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof typeof errors]) {
      setErrors((prev) => ({ ...prev, [name]: "" }));
    }
  };

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-50" />
      <div className="pointer-events-none absolute inset-0 bg-spotlight" />

      {/* Brand panel */}
      <div className="relative hidden lg:flex lg:w-1/2 lg:flex-col lg:justify-between lg:p-12">
        <Link href="/" className="flex w-fit items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/30">
            <GraduationCap className="h-5 w-5 text-primary" />
          </div>
          <span className="text-xl font-bold text-foreground">AcademIQ</span>
        </Link>

        <div className="space-y-8">
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
              Academic Intelligence
            </p>
            <h1 className="text-5xl font-bold leading-[1.1] tracking-tight text-foreground">
              Know your grades
              <br />
              <span className="text-primary">before</span> they happen.
            </h1>
            <p className="mt-5 max-w-sm text-base leading-relaxed text-muted-foreground">
              ML-powered insights from your Moodle data. Predict performance,
              spot burnout risk, and act before it&apos;s too late.
            </p>
          </div>

          <div className="flex flex-wrap gap-2.5">
            {[
              { icon: Brain, text: "AI Classification" },
              { icon: BarChart3, text: "Predicted Grades" },
              { icon: Zap, text: "Live Moodle Sync" },
            ].map(({ icon: Icon, text }) => (
              <div
                key={text}
                className="flex items-center gap-2.5 rounded-full border border-primary/20 bg-primary/5 px-4 py-2 text-sm text-muted-foreground"
              >
                <Icon className="h-3.5 w-3.5 text-primary" />
                {text}
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-muted-foreground/60">
          Sign in with your Student ID or Moodle email.
        </p>
      </div>

      {/* Form panel */}
      <div className="relative flex w-full items-center justify-center px-6 py-12 lg:w-1/2">
        <div className="absolute left-0 top-1/2 hidden h-[60%] w-px -translate-y-1/2 bg-gradient-to-b from-transparent via-border to-transparent lg:block" />

        <div className="w-full max-w-sm">
          <Link href="/" className="mb-10 flex items-center gap-2.5 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/30">
              <GraduationCap className="h-4 w-4 text-primary" />
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
            {errors.general ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {errors.general}
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="studentId" className="text-sm font-medium text-foreground/80">
                Student ID or email
              </Label>
              <Input
                id="studentId"
                name="studentId"
                type="text"
                value={formData.studentId}
                onChange={handleChange}
                placeholder="student1 or you@university.edu"
                className={`h-11 border-border/60 bg-input/50 placeholder:text-muted-foreground/40 focus-visible:border-primary/60 focus-visible:ring-1 focus-visible:ring-primary/30 ${
                  errors.studentId ? "border-destructive/60" : ""
                }`}
                disabled={isLoading}
                autoComplete="username"
              />
              {errors.studentId ? (
                <p className="text-xs text-destructive">{errors.studentId}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium text-foreground/80">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  className={`h-11 border-border/60 bg-input/50 pr-10 placeholder:text-muted-foreground/40 focus-visible:border-primary/60 focus-visible:ring-1 focus-visible:ring-primary/30 ${
                    errors.password ? "border-destructive/60" : ""
                  }`}
                  disabled={isLoading}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  disabled={isLoading}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.password ? (
                <p className="text-xs text-destructive">{errors.password}</p>
              ) : null}
            </div>

            <Button
              type="submit"
              className="h-11 w-full text-sm font-semibold glow-primary-sm"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                ctaText
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <SignInForm />
    </Suspense>
  );
}
