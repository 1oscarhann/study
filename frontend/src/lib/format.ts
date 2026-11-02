export function percent(accuracy: number | null | undefined): string {
  return accuracy == null ? "–" : `${Math.round(accuracy * 100)}%`;
}

export function daysLeftLabel(days: number): string {
  if (days <= 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `${days} days`;
}

export function shortDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export function comesBackIn(days: number): string {
  if (days <= 1) return "This question comes back tomorrow.";
  return `This question comes back in ${days} days.`;
}
