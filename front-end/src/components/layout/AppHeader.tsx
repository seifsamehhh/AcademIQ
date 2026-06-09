"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { GraduationCap, LogOut } from "lucide-react";
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
              "shrink-0 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
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
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      {/* Mobile: logo + logout on top, nav links on a full-width row below */}
      <div className="container md:hidden">
        <div className="flex h-14 items-center justify-between gap-4">
          <Link
            href="/dashboard"
            className="flex shrink-0 items-center gap-2 transition-opacity hover:opacity-80"
          >
            <GraduationCap className="h-7 w-7 text-primary" />
            <span className="text-lg font-bold text-foreground">AcademIQ</span>
          </Link>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
        <nav
          className="flex items-center gap-1 overflow-x-auto border-t border-border/40 py-2"
          aria-label="Student navigation"
        >
          <NavLinks pathname={pathname} />
        </nav>
      </div>

      {/* Desktop: single row — logo | nav links | logout */}
      <div className="container hidden h-16 items-center justify-between gap-6 md:flex">
        <Link
          href="/dashboard"
          className="flex shrink-0 items-center gap-2 transition-opacity hover:opacity-80"
        >
          <GraduationCap className="h-7 w-7 text-primary" />
          <span className="text-lg font-bold text-foreground">AcademIQ</span>
        </Link>

        <nav
          className="flex items-center gap-1"
          aria-label="Student navigation"
        >
          <NavLinks pathname={pathname} />
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          {user && (
            <span className="text-sm text-muted-foreground">{user.fullName}</span>
          )}
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
      </div>
    </header>
  );
}
