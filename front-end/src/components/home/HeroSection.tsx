import Link from "next/link";
import Image from "next/image";
import { ArrowRight, BarChart3, BookOpen, Shield } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PILLS = [
  { icon: BarChart3, label: "Performance Insights" },
  { icon: BookOpen, label: "Quiz Generation" },
  { icon: Shield, label: "Risk Guidance" },
];

export function HeroSection() {
  return (
    <section className="relative min-h-[600px] w-full overflow-hidden">
      <div className="absolute inset-0">
        <Image
          src="/hero-study.jpg"
          alt="Students studying together"
          fill
          priority
          className="object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-black/90 via-neutral-900/80 to-neutral-700/70" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
      </div>

      <div className="container relative z-10 flex min-h-[600px] flex-col items-center justify-center py-20 text-center">
        <h1 className="mb-6 max-w-4xl text-4xl font-bold leading-tight text-white md:text-5xl lg:text-6xl">
          Empower Your Academic Journey
        </h1>
        <p className="mb-8 max-w-2xl text-lg text-white/90 md:text-xl">
          A supplementary learning platform that works alongside your Moodle LMS.
          Review activity, generate practice quizzes, and access prediction support
          when the model service is available.
        </p>

        <div className="mb-10 flex flex-wrap justify-center gap-4">
          {PILLS.map(({ icon: Icon, label }) => (
            <div
              key={label}
              className="flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 backdrop-blur-sm"
            >
              <Icon className="h-5 w-5 text-white" />
              <span className="text-sm font-medium text-white">{label}</span>
            </div>
          ))}
        </div>

        <Link
          href="/signin"
          className={cn(
            buttonVariants({ variant: "light", size: "lg" }),
            "group",
          )}
        >
          Get Started
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </Link>
      </div>
    </section>
  );
}
