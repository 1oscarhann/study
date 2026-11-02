import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderRoute } from "./test/render";

function mockFetchJson(body: unknown, status = 200) {
  const fn = vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("app shell", () => {
  it("shows the five bottom-nav tabs", () => {
    mockFetchJson({ status: "ok", db: "ok" });
    renderRoute("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    const labels = within(nav).getAllByRole("link").map((a) => a.textContent);
    expect(labels).toEqual(["Home", "Revise", "Create", "Ranks", "Me"]);
  });

  it("marks the current tab and navigates between tabs", async () => {
    mockFetchJson({ status: "ok", db: "ok" });
    renderRoute("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");

    await userEvent.click(within(nav).getByRole("link", { name: "Ranks" }));
    expect(await screen.findByRole("heading", { name: "Ranks" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Ranks" })).toHaveAttribute("aria-current", "page");
  });

  it("shows a not-found page for unknown URLs", () => {
    mockFetchJson({ status: "ok", db: "ok" });
    renderRoute("/definitely-not-a-page");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

describe("home API status", () => {
  it("says the server is online when /api/health is ok", async () => {
    const fetchMock = mockFetchJson({ status: "ok", db: "ok" });
    renderRoute("/");
    expect(await screen.findByText("Server online")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/health");
    expect(new Headers(init.headers).get("X-Requested-With")).toBe("rb");
    expect(init.credentials).toBe("same-origin");
  });

  it("says the server is unavailable when the health check fails", async () => {
    mockFetchJson({ status: "degraded", db: "error" }, 503);
    renderRoute("/");
    expect(await screen.findByText("Server unavailable")).toBeInTheDocument();
  });
});
