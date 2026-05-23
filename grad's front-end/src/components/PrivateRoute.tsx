/**
 * PrivateRoute — guards authenticated-only pages.
 *
 * Usage in App.tsx:
 *   <Route path="/dashboard" element={<PrivateRoute><StudentDashboard /></PrivateRoute>} />
 *
 * Unauthenticated visitors are redirected to /signin.
 * After sign-in, React Router restores the originally requested path via `state.from`.
 */

import { Navigate, useLocation } from "react-router-dom";
import { useUser } from "@/context/UserContext";
import { ReactNode } from "react";

interface PrivateRouteProps {
  children: ReactNode;
}

const PrivateRoute = ({ children }: PrivateRouteProps) => {
  const { isAuthenticated } = useUser();
  const location = useLocation();

  if (!isAuthenticated) {
    // Pass current location so SignIn can redirect back after login
    return <Navigate to="/signin" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default PrivateRoute;
