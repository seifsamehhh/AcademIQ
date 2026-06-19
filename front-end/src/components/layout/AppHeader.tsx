"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { GraduationCap, LogOut, Brain } from "lucide-react";
import { useUser } from "@/context/UserContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/quiz", label: "Quiz Generation" },
  { href: "/performance", label: "Performance Analysis" },
];

function NavLinks({ pathname }: { pathname: string }) {
  return (
    <>
      {NAV.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              active
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useUser();

  const handleLogout = () => {
    signOut();
    router.replace("/signin");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 bg-background/80 backdrop-blur-xl">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

      <div className="container md:hidden">
        <div className="flex h-14 items-center justify-between gap-4">
          <Link
            href="/dashboard"
            className="group flex shrink-0 items-center gap-2.5 transition-opacity hover:opacity-80"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25 group-hover:ring-primary/50">
              <GraduationCap className="h-3.5 w-3.5 text-primary" />
            </div>
            <span className="text-sm font-bold tracking-tight text-foreground">
              AcademIQ
            </span>
          </Link>
          <Button variant="outline" size="sm" onClick={handleLogout} className="h-8">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
        <nav
          className="flex items-center gap-1 overflow-x-auto border-t border-border/40 py-2"
          aria-label="Student navigation"
        >
          <NavLinks pathname={pathname} />
        </nav>
      </div>

      <div className="container hidden h-14 items-center justify-between gap-6 md:flex">
        <Link
          href="/dashboard"
          className="group flex shrink-0 items-center gap-2.5 transition-opacity hover:opacity-80"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25 group-hover:ring-primary/50">
            <GraduationCap className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-sm font-bold tracking-tight text-foreground">
            AcademIQ
          </span>
        </Link>

        <nav className="flex items-center gap-1" aria-label="Student navigation">
          <NavLinks pathname={pathname} />
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <Link
            href="/insights"
            className="hidden items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground sm:flex"
          >
            <Brain className="h-3.5 w-3.5" />
            Insights
          </Link>
          {user ? (
            <span className="hidden max-w-[140px] truncate text-xs text-muted-foreground sm:inline">
              {user.fullName}
            </span>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={handleLogout}
            className="h-8 gap-1.5 border-border/60 bg-card/50 text-xs"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </Button>
        </div>
      </div>
    </header>
  );
}
