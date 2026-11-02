/**
 * Foundation/Higher choice, remembered per subject on this device only. It's a revision
 * preference, not personal data, so it never goes to the server.
 */
const key = (subjectId: number | null) => `rb:tier:${subjectId ?? "none"}`;

export function getIncludeHigher(subjectId: number | null): boolean {
  try {
    return localStorage.getItem(key(subjectId)) !== "foundation";
  } catch {
    return true;
  }
}

export function setIncludeHigher(subjectId: number | null, includeHigher: boolean): void {
  try {
    localStorage.setItem(key(subjectId), includeHigher ? "higher" : "foundation");
  } catch {
    // storage blocked (private mode etc.): the toggle still works for this visit
  }
}
