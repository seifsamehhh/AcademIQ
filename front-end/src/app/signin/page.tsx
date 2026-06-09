"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, GraduationCap, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
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
      next.studentId = "Student ID is required";
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
        general:
          err instanceof Error ? err.message : "Invalid login",
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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-auth-start to-auth-end p-4">
      <div className="w-full max-w-md">
        <div className="rounded-2xl bg-card p-8 shadow-2xl">
          <div className="mb-8 flex justify-center">
            <Link
              href="/"
              className="flex items-center gap-2 transition-opacity hover:opacity-80"
            >
              <GraduationCap className="h-8 w-8 text-primary" />
              <span className="text-xl font-bold text-foreground">AcademIQ</span>
            </Link>
          </div>

          <h1 className="mb-2 text-center text-2xl font-bold text-primary">
            Sign In
          </h1>
          <p className="mb-8 text-center text-sm text-muted-foreground">
            Sign in with your Student ID and password.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            {errors.general && (
              <div className="rounded-lg bg-destructive/10 p-3 text-center text-sm text-destructive">
                {errors.general}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="studentId">Student ID</Label>
              <Input
                id="studentId"
                name="studentId"
                type="text"
                value={formData.studentId}
                onChange={handleChange}
                placeholder="student1"
                className={
                  errors.studentId
                    ? "border-destructive focus-visible:ring-destructive"
                    : ""
                }
                disabled={isLoading}
                autoComplete="username"
              />
              {errors.studentId && (
                <p className="text-sm text-destructive">{errors.studentId}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  className={
                    errors.password
                      ? "border-destructive pr-10 focus-visible:ring-destructive"
                      : "pr-10"
                  }
                  disabled={isLoading}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  disabled={isLoading}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password}</p>
              )}
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing In...
                </>
              ) : (
                "Sign In"
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Demo: student1 / password123 or student2 / pass456
          </p>
        </div>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <SignInForm />
    </Suspense>
  );
}
