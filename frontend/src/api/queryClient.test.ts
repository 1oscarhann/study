import { describe, expect, it } from "vitest";

import { ApiError } from "./client";
import { isWakingUp } from "./queryClient";

describe("isWakingUp", () => {
  it("retries gateway errors and network failures", () => {
    expect(isWakingUp(new ApiError(502, "x"))).toBe(true);
    expect(isWakingUp(new ApiError(503, "x"))).toBe(true);
    expect(isWakingUp(new TypeError("Failed to fetch"))).toBe(true);
  });

  it("doesn't retry real client errors", () => {
    expect(isWakingUp(new ApiError(400, "bad"))).toBe(false);
    expect(isWakingUp(new ApiError(401, "nope"))).toBe(false);
    expect(isWakingUp(new ApiError(404, "gone"))).toBe(false);
  });
});
