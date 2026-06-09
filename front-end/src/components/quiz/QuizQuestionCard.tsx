"use client";

import { Check, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { QuizQuestion } from "@/lib/types";

interface Props {
  question: QuizQuestion;
  /** 1-based position, shown before the question text. */
  number: number;
  /** Currently chosen option index, or undefined if unanswered. */
  selectedIndex?: number;
  /** Once submitted, choices lock and correctness is revealed. */
  submitted: boolean;
  onSelect: (optionIndex: number) => void;
}

/** A single quiz question rendered as a self-contained, stacked card. */
export function QuizQuestionCard({
  question,
  number,
  selectedIndex,
  submitted,
  onSelect,
}: Props) {
  const answered = selectedIndex !== undefined;
  const isCorrectSelection =
    submitted && answered && selectedIndex === question.correctIndex;

  return (
    <Card>
      <CardContent className="space-y-5 p-5 sm:p-6">
        <p className="text-base font-medium leading-relaxed text-foreground">
          <span className="mr-2 font-semibold text-primary">{number}.</span>
          {question.question}
        </p>

        <div
          role="radiogroup"
          aria-label={`Question ${number}`}
          className="grid gap-3"
        >
          {question.options.map((option, oi) => {
            const selected = selectedIndex === oi;
            const isCorrectOption = oi === question.correctIndex;

            // Before submit: only show selection — never reveal the correct answer.
            const showPreSubmitSelected = !submitted && selected;

            // After submit: reveal correct answer and mark the student's choice.
            const showAsCorrect =
              submitted && isCorrectOption && (selected || !answered || !isCorrectSelection);
            const showAsWrong = submitted && selected && !isCorrectOption;

            return (
              <button
                key={oi}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => onSelect(oi)}
                disabled={submitted}
                className={cn(
                  "flex items-start justify-between gap-3 rounded-lg border px-4 py-3.5 text-left text-sm leading-relaxed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-default",
                  showPreSubmitSelected &&
                    "border-primary bg-primary/5 ring-1 ring-primary/20",
                  !submitted &&
                    !selected &&
                    "border-border bg-background hover:border-primary/30 hover:bg-accent/50",
                  showAsCorrect &&
                    "border-success bg-success/10 text-success",
                  showAsWrong &&
                    "border-destructive bg-destructive/10 text-destructive",
                  submitted &&
                    !showAsCorrect &&
                    !showAsWrong &&
                    "border-border bg-muted/30 text-muted-foreground",
                )}
              >
                <span className="flex-1">{option}</span>
                <span className="flex shrink-0 items-center gap-2">
                  {showPreSubmitSelected && !submitted ? (
                    <Badge variant="outline" className="text-xs">
                      Selected
                    </Badge>
                  ) : null}
                  {showAsWrong ? (
                    <>
                      <Badge variant="destructive" className="text-xs">
                        Your answer
                      </Badge>
                      <X className="h-4 w-4 shrink-0" aria-hidden />
                    </>
                  ) : null}
                  {showAsCorrect ? (
                    <>
                      <Badge
                        variant={selected ? "success" : "outline"}
                        className={cn(
                          "text-xs",
                          !selected && "border-success text-success",
                        )}
                      >
                        {selected ? "Correct" : "Correct answer"}
                      </Badge>
                      <Check className="h-4 w-4 shrink-0" aria-hidden />
                    </>
                  ) : null}
                </span>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
