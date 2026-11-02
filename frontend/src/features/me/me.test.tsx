import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { apiError, loggedInAs, ME, server } from "../../test/server";
import { renderRoute } from "../../test/render";

describe("settings", () => {
  it("shows your username and year", async () => {
    loggedInAs({ year_group: 11 });
    renderRoute("/me");
    expect(await screen.findByRole("heading", { name: "SwiftOtter42" })).toBeInTheDocument();
    expect(screen.getByText(/Year 11 · 0 XP/)).toBeInTheDocument();
  });

  it("changes the year group once, then locks it", async () => {
    loggedInAs({ year_group: 10 });
    let sent: unknown;
    server.use(
      http.patch("*/api/me/year-group", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ...ME, year_group: 11, can_change_year_group: false });
      }),
    );
    renderRoute("/me");
    await userEvent.selectOptions(await screen.findByLabelText("Your year group"), "11");
    await userEvent.click(screen.getByRole("button", { name: "Change to Year 11" }));
    expect(sent).toEqual({ year_group: 11 });
    expect(await screen.findByText(/You can change it again from 1 September/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Your year group")).not.toBeInTheDocument();
  });

  it("explains when you're graduated", async () => {
    loggedInAs({ year_group: null, graduated: true, can_change_year_group: false });
    renderRoute("/me");
    expect(await screen.findByText(/Graduated · not on leaderboards/)).toBeInTheDocument();
  });

  it("shows a wrong current password next to that field", async () => {
    loggedInAs();
    server.use(http.post("*/api/me/password", () => apiError(401, "That password isn't right.", "current_password")));
    renderRoute("/me");
    await userEvent.type(await screen.findByLabelText("Current password"), "nope nope");
    await userEvent.type(screen.getByLabelText("New password"), "brand new passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("That password isn't right.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveAttribute("aria-invalid", "true");
  });

  it("logs out back to the login page", async () => {
    let loggedIn = true;
    server.use(
      http.get("*/api/me", () => (loggedIn ? HttpResponse.json(ME) : apiError(401, "Please log in."))),
      http.post("*/api/auth/logout", () => {
        loggedIn = false;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderRoute("/me");
    await userEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("needs your password to delete the account", async () => {
    let body: unknown;
    server.use(
      http.get("*/api/me", () => HttpResponse.json(ME)),
      http.delete("*/api/me", async ({ request }) => {
        body = await request.json();
        server.use(http.get("*/api/me", () => apiError(401, "Please log in.")));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderRoute("/me");
    await userEvent.click(await screen.findByRole("button", { name: "Delete my account…" }));
    const forever = screen.getByRole("button", { name: "Delete forever" });
    expect(forever).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Type your password to confirm"), "correct horse battery");
    await userEvent.click(forever);
    expect(body).toEqual({ password: "correct horse battery" });
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });
});
