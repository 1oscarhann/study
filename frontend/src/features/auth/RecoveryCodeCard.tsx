import { useState } from "react";

import { Button } from "../../components/ui/Button";

interface RecoveryCodeCardProps {
  code: string;
  onDone: () => void;
  doneLabel?: string;
}

/** Shows a recovery code once, and won't move on until the student says they've saved it. */
export function RecoveryCodeCard({ code, onDone, doneLabel = "Continue" }: RecoveryCodeCardProps) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-bold tracking-tight">Save your recovery code</h2>
        <p className="text-muted">
          It's the only way back in if you forget your password. We can't see it or send it to you again.
        </p>
      </div>
      <div className="rounded-2xl border-2 border-dashed border-brand-500/60 bg-brand-50 p-4 text-center dark:bg-brand-500/10">
        {/* Wrap only between groups of four, never mid-group, so it's easy to copy down. */}
        <p
          className="flex select-all flex-wrap justify-center font-mono text-2xl font-bold tracking-wider text-[var(--ink)]"
          aria-label={`Recovery code ${code.split("").join(" ")}`}
          data-testid="recovery-code"
        >
          {code.split("-").map((group, i, all) => (
            <span key={i} className="whitespace-nowrap">
              {group}
              {i < all.length - 1 ? "-" : ""}
            </span>
          ))}
        </p>
      </div>
      <div className="flex gap-3">
        <Button variant="secondary" onClick={copy} className="flex-1">
          {copied ? "Copied" : "Copy code"}
        </Button>
      </div>
      <p className="text-sm text-muted">
        Write it down, screenshot it, or save it in your phone's notes. Keep it private.
      </p>
      <label className="flex min-h-12 items-center gap-3 rounded-xl border border-[var(--line)] px-4">
        <input
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
          className="size-5 accent-brand-600"
        />
        <span className="font-medium">I've saved my recovery code</span>
      </label>
      <Button block disabled={!saved} onClick={onDone}>
        {doneLabel}
      </Button>
    </div>
  );
}
