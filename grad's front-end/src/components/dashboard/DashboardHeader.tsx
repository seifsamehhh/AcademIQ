import { Link, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { GraduationCap, ChevronDown, Calendar, Award, BookOpen, LogOut, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuPortal,
} from "@/components/ui/dropdown-menu";
import { useUser } from "@/context/UserContext";
import { courses } from "@/data/mockData";

interface DashboardHeaderProps {
  username?: string;
}

const DashboardHeader = ({ username = "Student" }: DashboardHeaderProps) => {
  const navigate = useNavigate();
  const { logout } = useUser();

  const handleLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

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
          to="/dashboard"
          className="group flex items-center gap-2.5 transition-opacity hover:opacity-80"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25 transition-all group-hover:ring-primary/50">
            <GraduationCap className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-sm font-bold tracking-tight text-foreground">AcademIQ</span>
        </Link>

        {/* Nav */}
        <nav className="flex items-center gap-1">

          {/* Insights quick-link */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/student-insights")}
            className="hidden gap-2 text-muted-foreground hover:text-foreground sm:flex h-8 text-xs"
          >
            <Brain className="h-3.5 w-3.5" />
            AI Insights
          </Button>

          {/* My Courses */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-muted-foreground hover:text-foreground h-8 text-xs"
              >
                <BookOpen className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">My Courses</span>
                <ChevronDown className="h-3 w-3 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-56 border-border/60 bg-card/95 backdrop-blur-xl"
            >
              {courses.map((course) => (
                <DropdownMenuItem
                  key={course.id}
                  onClick={() => navigate(`/course/${course.id}`)}
                  className="cursor-pointer rounded-lg text-sm"
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium text-foreground">{course.code}</span>
                    <span className="text-xs text-muted-foreground">{course.name}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 border-border/60 bg-card/50 text-xs font-medium h-8 hover:bg-card hover:border-primary/30"
              >
                <div className="flex h-5 w-5 items-center justify-center rounded-md bg-primary/15 text-[10px] font-bold text-primary">
                  {username.charAt(0).toUpperCase()}
                </div>
                <span className="hidden sm:inline max-w-[100px] truncate">{username}</span>
                <ChevronDown className="h-3 w-3 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-48 border-border/60 bg-card/95 backdrop-blur-xl"
            >
              <DropdownMenuItem
                onClick={() => navigate("/schedule")}
                className="cursor-pointer gap-2 text-sm"
              >
                <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                Schedule
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => navigate("/grades")}
                className="cursor-pointer gap-2 text-sm"
              >
                <Award className="h-3.5 w-3.5 text-muted-foreground" />
                Grades
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-border/50" />
              <DropdownMenuSub>
                <DropdownMenuSubTrigger className="cursor-pointer gap-2 text-sm">
                  <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                  My Courses
                </DropdownMenuSubTrigger>
                <DropdownMenuPortal>
                  <DropdownMenuSubContent className="border-border/60 bg-card/95 backdrop-blur-xl">
                    {courses.map((course) => (
                      <DropdownMenuItem
                        key={course.id}
                        onClick={() => navigate(`/course/${course.id}`)}
                        className="cursor-pointer text-sm"
                      >
                        {course.code} — {course.name}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuPortal>
              </DropdownMenuSub>
              <DropdownMenuSeparator className="bg-border/50" />
              <DropdownMenuItem
                onClick={handleLogout}
                className="cursor-pointer gap-2 text-sm text-destructive focus:text-destructive"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>
      </div>
    </motion.header>
  );
};

export default DashboardHeader;
