import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { loggedInAs, server } from "./test/server";
import { renderRoute } from "./test/render";

describe("app shell (logged in)", () => {
  it("shows the five bottom-nav tabs", async () => {
    loggedInAs();
    renderRoute("/");
    const nav = await screen.findByRole("navigation", { name: "Main" });
    const labels = within(nav).getAllByRole("link").map((a) => a.textContent);
    expect(labels).toEqual(["Home", "Revise", "Create", "Ranks", "Me"]);
  });

  it("marks the current tab and navigates between tabs", async () => {
    loggedInAs();
    renderRoute("/");
    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");

    await userEvent.click(within(nav).getByRole("link", { name: "Ranks" }));
    expect(await screen.findByRole("heading", { name: "Ranks" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Ranks" })).toHaveAttribute("aria-current", "page");
  });

  it("greets you by username", async () => {
    loggedInAs({ username: "CosmicPanda11" });
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: /Hey CosmicPanda11/ })).toBeInTheDocument();
  });

  it("shows a not-found page for unknown URLs", async () => {
    loggedInAs();
    renderRoute("/definitely-not-a-page");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

describe("home API status", () => {
  it("says the server is online when /api/health is ok", async () => {
    loggedInAs();
    renderRoute("/");
    expect(await screen.findByText("Server online")).toBeInTheDocument();
  });

  it("says the server is unavailable when the health check fails", async () => {
    loggedInAs();
    server.use(http.get("*/api/health", () => HttpResponse.json({ status: "degraded", db: "error" }, { status: 503 })));
    renderRoute("/");
    expect(await screen.findByText("Server unavailable")).toBeInTheDocument();
  });
});

describe("api client", () => {
  it("sends the CSRF header and same-origin credentials", async () => {
    let seen: Request | undefined;
    server.use(
      http.get("*/api/me", ({ request }) => {
        seen = request;
        return HttpResponse.json({ detail: "Please log in.", code: "x", field: null }, { status: 401 });
      }),
    );
    renderRoute("/login");
    await screen.findByRole("heading", { name: "Welcome back" });
    expect(seen?.headers.get("X-Requested-With")).toBe("rb");
    expect(seen?.credentials).toBe("same-origin");
  });
});
