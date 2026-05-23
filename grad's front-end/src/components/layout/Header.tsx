import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";

const Header = () => {
  return (
    <motion.header
      initial={{ y: -8, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="sticky top-0 z-50 w-full border-b border-border/50 bg-background/80 backdrop-blur-xl"
    >
      {/* Top glow line */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

      <div className="container flex h-14 items-center justify-between">
        {/* Logo */}
        <Link
          to="/"
          className="group flex items-center gap-2.5 transition-opacity hover:opacity-80"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25 transition-all group-hover:ring-primary/50">
            <GraduationCap className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-sm font-bold tracking-tight text-foreground">AcademIQ</span>
        </Link>

        {/* CTA */}
        <Button
          asChild
          size="sm"
          className="h-8 bg-primary px-4 text-xs font-semibold text-primary-foreground
            hover:bg-primary/90 glow-primary-sm"
        >
          <Link to="/signin">Sign In</Link>
        </Button>
      </div>
    </motion.header>
  );
};

export default Header;
