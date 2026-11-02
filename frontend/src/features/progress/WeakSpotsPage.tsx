import { errorMessage } from "../../api/client";
import { useStartPlay, useWeakSpots } from "../../api/learn";
import type { WeakSpot } from "../../api/types";
import { AccuracyBar, Loading, PageTitle } from "../../components/ui/Bits";
import { Button } from "../../components/ui/Button";
import { FormError } from "../../components/ui/Field";
import { percent } from "../../lib/format";
import { getIncludeHigher } from "../../lib/tier";

function SpotRow({ spot, onRevise, busy }: { spot: WeakSpot; onRevise: () => void; busy: boolean }) {
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{spot.name}</p>
          <p className="text-xs text-muted">
            {spot.subject_name} · {spot.correct}/{spot.answered} right
          </p>
        </div>
        <span className="shrink-0 text-lg font-bold tabular-nums">{percent(spot.accuracy)}</span>
      </div>
      <AccuracyBar accuracy={spot.accuracy} />
      <Button variant="secondary" className="!min-h-10 w-full text-sm" loading={busy} onClick={onRevise}>
        Revise this
      </Button>
    </li>
  );
}

export function WeakSpotsPage() {
  const { data, isPending, error } = useWeakSpots();
  const start = useStartPlay();
  const ranked = data?.topics.filter((t) => t.enough_data) ?? [];
  const early = data?.topics.filter((t) => !t.enough_data) ?? [];

  function revise(spot: WeakSpot) {
    start.mutate({
      mode: "quiz",
      topic_id: spot.topic_id,
      subject_id: spot.subject_id,
      include_higher: getIncludeHigher(spot.subject_id),
    });
  }

  return (
    <div className="space-y-5">
      <PageTitle back={{ to: "/revise", label: "Revise" }}>Weak spots</PageTitle>
      {isPending && <Loading />}
      <FormError message={error ? errorMessage(error) : start.error ? errorMessage(start.error) : null} />
      {data && data.topics.length === 0 && (
        <p className="card p-4 text-muted">
          Play a few quizzes and your weakest topics will show up here, worst first.
        </p>
      )}
      {ranked.length > 0 && (
        <section className="space-y-2">
          <p className="text-sm text-muted">Your accuracy over the last {data?.window_days} days, worst first.</p>
          <ol className="card divide-y divide-[var(--line)]">
            {ranked.map((spot) => (
              <SpotRow key={spot.topic_id} spot={spot} busy={start.isPending} onRevise={() => revise(spot)} />
            ))}
          </ol>
        </section>
      )}
      {early.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Not enough answers yet (need {data?.min_answers})
          </h2>
          <ul className="card divide-y divide-[var(--line)]">
            {early.map((spot) => (
              <SpotRow key={spot.topic_id} spot={spot} busy={start.isPending} onRevise={() => revise(spot)} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
