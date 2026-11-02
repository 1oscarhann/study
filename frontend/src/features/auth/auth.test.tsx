import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, ME, server } from "../../test/server";
import { renderRoute } from "../../test/render";
import { safeNext } from "./safeNext";
import { isSummerHoliday } from "./SignupPage";

afterEach(() => vi.useRealTimers());

describe("route guards", () => {
  it("sends logged-out visitors to the login page", async () => {
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("remembers where you were going", async () => {
    let loggedIn = false;
    server.use(
      http.get("*/api/me", () => (loggedIn ? HttpResponse.json(ME) : apiError(401, "Please log in."))),
      http.post("*/api/auth/login", () => {
        loggedIn = true;
        return HttpResponse.json({ user: ME });
      }),
    );
    renderRoute("/ranks");
    await userEvent.type(await screen.findByLabelText("Username"), "SwiftOtter42");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("heading", { name: "Ranks" })).toBeInTheDocument();
  });

  it("only redirects to paths on this site", () => {
    expect(safeNext("/ranks")).toBe("/ranks");
    expect(safeNext("//evil.example")).toBe("/");
    expect(safeNext("https://evil.example")).toBe("/");
    expect(safeNext("/\\evil.example")).toBe("/");
    expect(safeNext(null)).toBe("/");
  });
});

describe("login", () => {
  it("shows the server's message when the details are wrong", async () => {
    server.use(http.post("*/api/auth/login", () => apiError(401, "Wrong username or password.")));
    renderRoute("/login");
    await userEvent.type(await screen.findByLabelText("Username"), "SwiftOtter42");
    await userEvent.type(screen.getByLabelText("Password"), "nope nope");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");
  });

  it("explains rate limiting", async () => {
    server.use(http.post("*/api/auth/login", () => apiError(429, "Too many attempts. Try again in 12 minutes.")));
    renderRoute("/login");
    await userEvent.type(await screen.findByLabelText("Username"), "SwiftOtter42");
    await userEvent.type(screen.getByLabelText("Password"), "nope nope");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 12 minutes");
  });
});

describe("signup", () => {
  it("only offers Years 7 to 13", async () => {
    renderRoute("/signup");
    const select = await screen.findByLabelText("Year group");
    const options = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual([
      "Choose your year",
      "Year 7",
      "Year 8",
      "Year 9",
      "Year 10",
      "Year 11",
      "Year 12",
      "Year 13",
    ]);
  });

  it("suggests usernames and fills one in", async () => {
    server.use(http.get("*/api/auth/username-ideas", () => HttpResponse.json({ ideas: ["CosmicPanda11", "BraveOwl23"] })));
    renderRoute("/signup");
    await userEvent.click(await screen.findByRole("button", { name: "Suggest a username" }));
    await userEvent.click(await screen.findByRole("button", { name: "BraveOwl23" }));
    expect(screen.getByLabelText("Username")).toHaveValue("BraveOwl23");
  });

  it("shows the recovery code and won't continue until it's saved", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/auth/signup", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ user: ME, recovery_code: "ABCD-EFGH-JKMN-PQRS" }, { status: 201 });
      }),
    );
    renderRoute("/signup");
    await userEvent.type(await screen.findByLabelText("Username"), "SwiftOtter42");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.selectOptions(screen.getByLabelText("Year group"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(body).toEqual({ username: "SwiftOtter42", password: "correct horse battery", year_group: 10 });
    expect(await screen.findByTestId("recovery-code")).toHaveTextContent("ABCD-EFGH-JKMN-PQRS");
    const go = screen.getByRole("button", { name: "Start revising" });
    expect(go).toBeDisabled();

    await userEvent.click(screen.getByLabelText("I've saved my recovery code"));
    await userEvent.click(go);
    expect(await screen.findByRole("heading", { name: /Hey SwiftOtter42/ })).toBeInTheDocument();
  });

  it("puts field errors next to the right field", async () => {
    server.use(
      http.post("*/api/auth/signup", () => apiError(409, "That username's taken. Try another.", "username")),
    );
    renderRoute("/signup");
    await userEvent.type(await screen.findByLabelText("Username"), "SwiftOtter42");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.selectOptions(screen.getByLabelText("Year group"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    const username = screen.getByLabelText("Username");
    expect(await screen.findByText("That username's taken. Try another.")).toBeInTheDocument();
    expect(username).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains which year to pick during the summer holidays", () => {
    expect(isSummerHoliday(new Date(2027, 7, 15))).toBe(true); // 15 Aug
    expect(isSummerHoliday(new Date(2027, 6, 25))).toBe(true); // 25 Jul
    expect(isSummerHoliday(new Date(2027, 8, 1))).toBe(false); // 1 Sep
    expect(isSummerHoliday(new Date(2027, 2, 1))).toBe(false);
  });

  it("skips signup if you're already logged in", async () => {
    server.use(http.get("*/api/me", () => HttpResponse.json(ME)));
    renderRoute("/signup");
    expect(await screen.findByRole("heading", { name: /Hey SwiftOtter42/ })).toBeInTheDocument();
  });
});

describe("recover", () => {
  it("resets the password and shows the new recovery code", async () => {
    server.use(
      http.post("*/api/auth/recover", () => HttpResponse.json({ user: ME, recovery_code: "WXYZ-2345-6789-ABCD" })),
    );
    renderRoute("/recover");
    await userEvent.type(await screen.findByLabelText("Username"), "SwiftOtter42");
    await userEvent.type(screen.getByLabelText("Recovery code"), "abcd efgh jkmn pqrs");
    await userEvent.type(screen.getByLabelText("New password"), "brand new passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByTestId("recovery-code")).toHaveTextContent("WXYZ-2345-6789-ABCD");
  });
});
