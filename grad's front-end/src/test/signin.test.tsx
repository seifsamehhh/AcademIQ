/**
 * signin.test.tsx — Functional tests for the SignIn form.
 *
 * Tests: validation logic, loading state, navigation after success.
 * Uses React Testing Library + Vitest.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { UserProvider } from "@/context/UserContext";
import SignIn from "@/pages/SignIn";

// ── Mocks ────────────────────────────────────────────────────

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: null, pathname: "/signin" }),
  };
});

// Pin the A/B variant to "control" so button text is always "Sign In"
vi.mock("@/hooks/useABTest", () => ({
  useABTest: () => ({ variant: "control", isControl: true, isVariantA: false }),
}));

// ── Helper ───────────────────────────────────────────────────

const renderSignIn = () =>
  render(
    <MemoryRouter initialEntries={["/signin"]}>
      <UserProvider>
        <SignIn />
      </UserProvider>
    </MemoryRouter>
  );

// ── Tests ────────────────────────────────────────────────────

describe("SignIn — form rendering", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    localStorage.clear();
  });

  it("renders the username input", () => {
    renderSignIn();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  });

  it("renders the password input", () => {
    renderSignIn();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    renderSignIn();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});

describe("SignIn — validation: username", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    localStorage.clear();
  });

  it("shows error when username is empty on submit", async () => {
    renderSignIn();
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
    });
  });

  it("shows error when username has fewer than 3 characters", async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), "ab");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText(/at least 3 characters/i)).toBeInTheDocument();
    });
  });

  it("clears username error when user starts typing", async () => {
    renderSignIn();
    // Trigger error first
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => screen.getByText(/username is required/i));
    // Type to clear
    await userEvent.type(screen.getByLabelText(/username/i), "nour");
    await waitFor(() => {
      expect(screen.queryByText(/username is required/i)).not.toBeInTheDocument();
    });
  });
});

describe("SignIn — validation: password", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    localStorage.clear();
  });

  it("shows error when password is empty on submit", async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), "nour123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  it("shows error when password has fewer than 6 characters", async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), "nour123");
    await userEvent.type(screen.getByLabelText(/password/i), "123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText(/at least 6 characters/i)).toBeInTheDocument();
    });
  });
});

describe("SignIn — successful submit", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    localStorage.clear();
  });

  it("saves username to localStorage after valid submit", async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), "nour_test");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(localStorage.getItem("academiq_username")).toBe("nour_test");
    }, { timeout: 2000 });
  });

  it("navigates to /dashboard after valid submit", async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), "nour_test");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    }, { timeout: 2000 });
  });

  it("shows loading state while submitting", async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), "nour_test");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    // Loading text should appear briefly
    expect(screen.getByText(/signing in/i)).toBeInTheDocument();
  });
});
