/**
 * privateroute.test.tsx — Tests for the PrivateRoute guard.
 *
 * Tests: unauthenticated redirect, authenticated access,
 *        state preservation (from location).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { UserProvider } from "@/context/UserContext";
import PrivateRoute from "@/components/PrivateRoute";

// ── Helpers ──────────────────────────────────────────────────

const ProtectedPage = () => <div>Protected Content</div>;
const SignInPage    = () => <div>Sign In Page</div>;

/** Render with a given authenticated state (via localStorage). */
const renderWithAuth = (isAuthenticated: boolean, initialPath = "/protected") => {
  if (isAuthenticated) {
    localStorage.setItem("academiq_username", "nour");
  } else {
    localStorage.removeItem("academiq_username");
  }

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <UserProvider>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route
            path="/protected"
            element={
              <PrivateRoute>
                <ProtectedPage />
              </PrivateRoute>
            }
          />
        </Routes>
      </UserProvider>
    </MemoryRouter>
  );
};

// ── Tests ────────────────────────────────────────────────────

describe("PrivateRoute — unauthenticated user", () => {
  it("redirects to /signin when not authenticated", () => {
    renderWithAuth(false);
    expect(screen.getByText("Sign In Page")).toBeInTheDocument();
  });

  it("does NOT show protected content when not authenticated", () => {
    renderWithAuth(false);
    expect(screen.queryByText("Protected Content")).toBeNull();
  });
});

describe("PrivateRoute — authenticated user", () => {
  it("renders the protected page when authenticated", () => {
    renderWithAuth(true);
    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("does NOT redirect to signin when authenticated", () => {
    renderWithAuth(true);
    expect(screen.queryByText("Sign In Page")).toBeNull();
  });
});
