import type { ReactNode } from "react";

interface ComingSoonProps {
  title: string;
  phase: number;
  children?: ReactNode;
}

export function ComingSoon({ title, phase, children }: ComingSoonProps) {
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      <div className="card p-5">
        <p className="text-muted">
          {children ?? "This screen is on its way."}{" "}
          <span className="whitespace-nowrap">(Phase {phase})</span>
        </p>
      </div>
    </section>
  );
}
