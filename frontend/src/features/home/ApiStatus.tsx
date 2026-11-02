import { useHealth } from "../../api/health";

/** Small pill proving the frontend → proxy → API → database chain works. */
export function ApiStatus() {
  const { data, isPending, isError } = useHealth();

  let tone = "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300";
  let label = "Connecting to server…";
  if (data?.status === "ok") {
    tone = "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300";
    label = "Server online";
  } else if (isError || (!isPending && data?.status !== "ok")) {
    tone = "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300";
    label = "Server unavailable";
  }

  return (
    <p role="status" className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${tone}`}>
      <span className="size-2 rounded-full bg-current" aria-hidden="true" />
      {label}
    </p>
  );
}
