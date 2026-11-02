import { errorMessage } from "../../api/client";
import { useStartPlay } from "../../api/learn";
import type { Home } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { FormError } from "../../components/ui/Field";

export function ReviewCard({ due, compact = false }: { due: Home["due_reviews"]; compact?: boolean }) {
  const start = useStartPlay();
  if (due.today === 0) {
    if (compact) return null;
    return (
      <section className="card p-4">
        <h2 className="font-bold">Reviews</h2>
        <p className="text-sm text-muted">
          {due.this_week > 0
            ? `All caught up! ${due.this_week} coming back this week.`
            : "All caught up. Questions you get wrong come back here."}
        </p>
      </section>
    );
  }
  return (
    <section className="card flex items-center gap-4 border-brand-500/50 bg-brand-50 p-4 dark:bg-brand-500/10">
      <div className="min-w-0 flex-1">
        <h2 className="font-bold">
          {due.today} {due.today === 1 ? "question" : "questions"} to review
        </h2>
        <p className="text-sm text-muted">Spaced repetition: review now to lock them in.</p>
        <FormError message={start.error ? errorMessage(start.error) : null} />
      </div>
      <Button loading={start.isPending} onClick={() => start.mutate({ mode: "review" })}>
        Review
      </Button>
    </section>
  );
}
