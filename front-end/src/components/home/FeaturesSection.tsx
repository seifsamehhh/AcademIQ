import {
  AlertTriangle,
  Brain,
  FileQuestion,
  TrendingUp,
} from "lucide-react";

const FEATURES = [
  {
    icon: TrendingUp,
    title: "Grade Prediction",
    description:
      "Performance insights and prediction support when the model service is available, alongside your Moodle course data.",
  },
  {
    icon: Brain,
    title: "Performance Insights",
    description:
      "Rule-based and model-driven guidance to highlight engagement patterns and areas to improve when analytics are available.",
  },
  {
    icon: AlertTriangle,
    title: "Burnout Detection",
    description:
      "Study workload signals across courses can flag burnout risk when behavioural data has been synced from Moodle.",
  },
  {
    icon: FileQuestion,
    title: "Quiz Generation",
    description:
      "Generate practice quizzes from your own lecture materials to revise exactly what you were taught.",
  },
];

export function FeaturesSection() {
  return (
    <section className="py-20">
      <div className="container">
        <div className="mb-12 text-center">
          <h2 className="mb-4 text-3xl font-bold text-foreground md:text-4xl">
            Why Choose AcademIQ?
          </h2>
          <p className="mx-auto max-w-2xl text-muted-foreground">
            AcademIQ works alongside your university&apos;s Moodle LMS to turn synced
            activity into clear, actionable guidance — so you can study smarter,
            not just harder.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="group rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/50 hover:shadow-lg"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                <Icon className="h-6 w-6 text-primary" />
              </div>
              <h3 className="mb-2 font-semibold text-card-foreground">{title}</h3>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
