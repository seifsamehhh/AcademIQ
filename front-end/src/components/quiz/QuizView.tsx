"use client";

import { useRef, useState } from "react";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { QuizQuestionCard } from "./QuizQuestionCard";
import type { GeneratedQuiz } from "@/lib/types";

export function QuizView({ quiz }: { quiz: GeneratedQuiz }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const topRef = useRef<HTMLDivElement>(null);

  const allAnswered = quiz.questions.every((q) => q.id in answers);
  const score = quiz.questions.reduce(
    (acc, q) => acc + (answers[q.id] === q.correctIndex ? 1 : 0),
    0,
  );

  const select = (questionId: string, optionIndex: number) => {
    if (submitted) return;
    setAnswers((prev) => ({ ...prev, [questionId]: optionIndex }));
  };

  const scrollToTop = () => {
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleSubmit = () => {
    setSubmitted(true);
    scrollToTop();
  };

  const handleRetry = () => {
    setAnswers({});
    setSubmitted(false);
    scrollToTop();
  };

  return (
    <div ref={topRef} className="scroll-mt-6 space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-4">
            <div>
              <CardTitle>Generated Quiz</CardTitle>
              <CardDescription>
                {quiz.questions.length} questions from {quiz.materialIds.length} material
                {quiz.materialIds.length === 1 ? "" : "s"}
              </CardDescription>
              {quiz.limitedQuizNote ? (
                <p className="mt-2 text-sm text-muted-foreground">{quiz.limitedQuizNote}</p>
              ) : null}
            </div>
            {submitted && (
              <Badge
                variant={score === quiz.questions.length ? "success" : "default"}
                className="shrink-0 text-sm"
              >
                {score} / {quiz.questions.length}
              </Badge>
            )}
          </div>
        </CardHeader>
      </Card>

      {quiz.questions.map((q, qi) => (
        <QuizQuestionCard
          key={q.id}
          question={q}
          number={qi + 1}
          selectedIndex={answers[q.id]}
          submitted={submitted}
          onSelect={(oi) => select(q.id, oi)}
        />
      ))}

      <div className="pt-2">
        {submitted ? (
          <Button variant="outline" onClick={handleRetry}>
            Retry quiz
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={!allAnswered}>
            Submit answers
          </Button>
        )}
      </div>
    </div>
  );
}
