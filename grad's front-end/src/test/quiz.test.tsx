/**
 * quiz.test.tsx — Functional tests for the GeneratedQuizzes quiz player.
 *
 * Component behaviour:
 * - 600ms loading skeleton, then shows quiz player
 * - "Next" / "Previous" navigation between questions
 * - "Submit Quiz" button on the last question
 * - After submit: score shown in sidebar + "Retake" button
 * - Timer auto-submits at 0
 *
 * We use real timers throughout (the 600ms loading is fast enough).
 * The auto-submit test advances fake timers in an isolated describe block.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { UserProvider } from "@/context/UserContext";
import GeneratedQuizzes from "@/pages/GeneratedQuizzes";

// ── Mock: 2-question quiz (fast, deterministic) ──────────────

vi.mock("@/data/mockData", async () => {
  const actual = await vi.importActual("@/data/mockData");
  return {
    ...actual,
    quizQuestionBank: {
      cs101: [
        {
          id: "q1",
          question: "What does OOP stand for?",
          options: [
            "Open Object Programming",
            "Object-Oriented Programming",
            "Ordered Object Processing",
            "Optional Output Parameter",
          ],
          correctIndex: 1,
        },
        {
          id: "q2",
          question: "Which loop runs at least once?",
          options: ["for", "while", "do...while", "foreach"],
          correctIndex: 2,
        },
      ],
    },
  };
});

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// ── Helpers ──────────────────────────────────────────────────

const renderQuizPage = () =>
  render(
    <MemoryRouter initialEntries={["/generated-quizzes"]}>
      <UserProvider>
        <Routes>
          <Route path="/generated-quizzes" element={<GeneratedQuizzes />} />
        </Routes>
      </UserProvider>
    </MemoryRouter>
  );

/** Render and wait for the 600ms loading skeleton to resolve. */
const renderAndLoad = async () => {
  const result = renderQuizPage();
  await waitFor(
    () => expect(screen.getByText(/What does OOP stand for/i)).toBeInTheDocument(),
    { timeout: 3000 }
  );
  return result;
};

/** Answer both questions and submit the quiz. */
const submitQuiz = async (q1AnswerText = "Object-Oriented Programming", q2AnswerText = "do...while") => {
  await renderAndLoad();

  // Q1
  fireEvent.click(screen.getByText(q1AnswerText));
  fireEvent.click(screen.getByRole("button", { name: /next/i }));

  // Q2
  await waitFor(() => screen.getByText(/Which loop runs at least once/i));
  fireEvent.click(screen.getByText(q2AnswerText));
  fireEvent.click(screen.getByRole("button", { name: /submit quiz/i }));

  // Wait for retake to appear (confirms submission)
  await waitFor(() => screen.getByRole("button", { name: /retake/i }));
};

beforeEach(() => {
  mockNavigate.mockClear();
  localStorage.clear();
});

// ── Rendering ─────────────────────────────────────────────────

describe("GeneratedQuizzes — rendering", () => {
  it("shows the first question after loading", async () => {
    await renderAndLoad();
    expect(screen.getByText(/What does OOP stand for/i)).toBeInTheDocument();
  });

  it("shows all 4 answer options for the first question", async () => {
    await renderAndLoad();
    expect(screen.getByText("Object-Oriented Programming")).toBeInTheDocument();
    expect(screen.getByText("Open Object Programming")).toBeInTheDocument();
    expect(screen.getByText("Ordered Object Processing")).toBeInTheDocument();
    expect(screen.getByText("Optional Output Parameter")).toBeInTheDocument();
  });

  it('shows "Question 1 of 2" counter', async () => {
    await renderAndLoad();
    expect(screen.getByText(/Question 1 of 2/i)).toBeInTheDocument();
  });

  it("displays the countdown timer", async () => {
    await renderAndLoad();
    // Timer starts at 15:00
    expect(screen.getByText(/15:\d\d/)).toBeInTheDocument();
  });
});

// ── Navigation ────────────────────────────────────────────────

describe("GeneratedQuizzes — navigation", () => {
  it('shows "Next" button on question 1', async () => {
    await renderAndLoad();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it('"Previous" is disabled on question 1', async () => {
    await renderAndLoad();
    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
  });

  it("clicking Next shows question 2", async () => {
    await renderAndLoad();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(screen.getByText(/Which loop runs at least once/i)).toBeInTheDocument()
    );
  });

  it('"Submit Quiz" appears on the last question', async () => {
    await renderAndLoad();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit quiz/i })).toBeInTheDocument()
    );
  });
});

// ── Scoring ───────────────────────────────────────────────────

describe("GeneratedQuizzes — scoring", () => {
  it("shows score in sidebar after submitting (all correct)", async () => {
    await submitQuiz();
    // Score block shows "{score}/{questions.length}" = "2/2"
    // Look for the "Your Score" label
    expect(screen.getByText(/your score/i)).toBeInTheDocument();
  });

  it("answer options are disabled after submission", async () => {
    await submitQuiz();
    const disabledBtns = screen
      .getAllByRole("button")
      .filter((b) => b.hasAttribute("disabled"));
    expect(disabledBtns.length).toBeGreaterThan(0);
  });
});

// ── Retake ────────────────────────────────────────────────────

describe("GeneratedQuizzes — retake", () => {
  it('shows "Retake" button after submission', async () => {
    await submitQuiz();
    expect(screen.getByRole("button", { name: /retake/i })).toBeInTheDocument();
  });

  it("clicking Retake resets to question 1", async () => {
    await submitQuiz();
    fireEvent.click(screen.getByRole("button", { name: /retake/i }));
    await waitFor(() =>
      expect(screen.getByText(/Question 1 of 2/i)).toBeInTheDocument()
    );
  });

  it("clicking Retake removes the score sidebar", async () => {
    await submitQuiz();
    fireEvent.click(screen.getByRole("button", { name: /retake/i }));
    await waitFor(() =>
      expect(screen.queryByText(/your score/i)).not.toBeInTheDocument()
    );
  });
});

// ── Auto-submit (timer) ───────────────────────────────────────

describe("GeneratedQuizzes — timer auto-submit", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("auto-submits when timer reaches 0", async () => {
    renderQuizPage();

    // Advance past the 600ms loading delay and flush React updates
    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    // Advance 15 minutes + 2 seconds to trigger auto-submit, then flush
    await act(async () => {
      vi.advanceTimersByTime(902_000);
    });

    // Check directly — act() already flushed all React state updates
    // so no waitFor needed (which would block with fake timers)
    expect(screen.getByRole("button", { name: /retake/i })).toBeInTheDocument();
  }, 15_000);
});
