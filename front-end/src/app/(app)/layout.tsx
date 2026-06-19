import { AppHeader } from "@/components/layout/AppHeader";
import { AuthGuard } from "@/components/layout/AuthGuard";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="relative flex min-h-screen flex-col bg-background">
        <div className="pointer-events-none fixed inset-0 bg-spotlight opacity-50" />
        <AppHeader />
        <main className="relative flex-1">
          <div className="container py-8">{children}</div>
        </main>
      </div>
    </AuthGuard>
  );
}
