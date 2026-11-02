import { ApiError, errorMessage } from "../../api/client";

/**
 * Split a mutation error into "this field is wrong" vs "general problem", so messages
 * show next to the right input.
 */
export function formErrors<F extends string>(error: unknown, fields: readonly F[]) {
  const byField: Partial<Record<F, string>> = {};
  let general: string | null = null;
  if (error) {
    if (error instanceof ApiError && error.field && (fields as readonly string[]).includes(error.field)) {
      byField[error.field as F] = error.message;
    } else {
      general = errorMessage(error);
    }
  }
  return { field: (name: F) => byField[name] ?? null, general };
}
