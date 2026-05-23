import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { UserProvider } from "@/context/UserContext";
import PrivateRoute from "@/components/PrivateRoute";
import Index from "./pages/Index";
import SignIn from "./pages/SignIn";
import StudentDashboard from "./pages/StudentDashboard";
import CoursePage from "./pages/CoursePage";
import Schedule from "./pages/Schedule";
import Grades from "./pages/Grades";
import GeneratedQuizzes from "./pages/GeneratedQuizzes";
import GeneratedNotes from "./pages/GeneratedNotes";
import StudentInsights from "./pages/StudentInsights";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

// ── Route-level fade transition ────────────────────────────────────────────────
const AnimatedRoutes = () => {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18, ease: "easeInOut" }}
        style={{ minHeight: "100vh" }}
      >
        <Routes location={location}>
          {/* Public routes */}
          <Route path="/" element={<Index />} />
          <Route path="/signin" element={<SignIn />} />

          {/* Protected routes — redirect to /signin if not authenticated */}
          <Route path="/dashboard" element={<PrivateRoute><StudentDashboard /></PrivateRoute>} />
          <Route path="/course/:courseId" element={<PrivateRoute><CoursePage /></PrivateRoute>} />
          <Route path="/schedule" element={<PrivateRoute><Schedule /></PrivateRoute>} />
          <Route path="/grades" element={<PrivateRoute><Grades /></PrivateRoute>} />
          <Route path="/generated-quizzes" element={<PrivateRoute><GeneratedQuizzes /></PrivateRoute>} />
          <Route path="/generated-notes" element={<PrivateRoute><GeneratedNotes /></PrivateRoute>} />
          <Route path="/student-insights" element={<PrivateRoute><StudentInsights /></PrivateRoute>} />

          {/* Catch-all */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <UserProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AnimatedRoutes />
        </BrowserRouter>
      </TooltipProvider>
    </UserProvider>
  </QueryClientProvider>
);

export default App;
