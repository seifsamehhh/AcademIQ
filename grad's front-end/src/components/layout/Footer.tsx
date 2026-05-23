import { Link } from "react-router-dom";
import { GraduationCap } from "lucide-react";

const Footer = () => {
  const year = new Date().getFullYear();

  return (
    <footer className="relative border-t border-border/40 bg-background">
      {/* Top glow */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />

      <div className="container flex flex-col items-center justify-between gap-4 py-6 sm:flex-row">
        {/* Wordmark */}
        <Link to="/" className="flex items-center gap-2 opacity-60 transition-opacity hover:opacity-100">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 ring-1 ring-primary/20">
            <GraduationCap className="h-3 w-3 text-primary" />
          </div>
          <span className="text-xs font-semibold tracking-tight text-foreground">AcademIQ</span>
        </Link>

        {/* Copyright */}
        <p className="text-xs text-muted-foreground/50">
          © {year} AcademIQ — Graduation Project
        </p>

        {/* Right: tiny links */}
        <nav className="flex items-center gap-4 text-xs text-muted-foreground/50">
          <a href="#" className="transition-colors hover:text-muted-foreground">Privacy</a>
          <a href="#" className="transition-colors hover:text-muted-foreground">Contact</a>
        </nav>
      </div>
    </footer>
  );
};

export default Footer;
