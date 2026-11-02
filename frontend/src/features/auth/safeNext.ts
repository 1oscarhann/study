/** Only ever redirect to a path on this site (no `//evil.com` or `https://…`). */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  return next;
}
