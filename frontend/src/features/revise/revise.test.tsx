import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { BIOLOGY, CELLS, MCQ, SUBJECTS, playState } from "../../test/fixtures";
import { renderRoute } from "../../test/render";
import { loggedInAs, server } from "../../test/server";

beforeEach(() => localStorage.clear());

describe("revise", () => {
  it("groups subjects into ready and coming soon", async () => {
    loggedInAs();
    server.use(http.get("*/api/subjects", () => HttpResponse.json({ subjects: SUBJECTS })));
    renderRoute("/revise");
    const ready = await screen.findByRole("heading", { name: "Ready to play" });
    expect(within(ready.parentElement!).getByRole("link", { name: /Biology/ })).toHaveTextContent("1 ready");
    const soon = screen.getByRole("heading", { name: "Questions coming soon" });
    expect(within(soon.parentElement!).getByRole("link", { name: /Mathematics/ })).toBeInTheDocument();
  });

  it("only links topics that have questions", async () => {
    loggedInAs();
    server.use(http.get("*/api/subjects/1", () => HttpResponse.json(BIOLOGY)));
    renderRoute("/revise/1");
    expect(await screen.findByRole("link", { name: /Cell biology/ })).toHaveAttribute("href", "/revise/1/10");
    expect(screen.getByText("Organisation").closest("a")).toBeNull();
    expect(screen.getByText("No questions yet")).toBeInTheDocument();
  });

  it("remembers Foundation per subject and sends it with the quiz", async () => {
    loggedInAs();
    let sent: unknown;
    server.use(
      http.get("*/api/topics/10", () => HttpResponse.json(CELLS)),
      http.post("*/api/play", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(playState(MCQ), { status: 201 });
      }),
    );
    renderRoute("/revise/1/10");
    await userEvent.click(await screen.findByRole("radio", { name: "Foundation" }));
    expect(localStorage.getItem("rb:tier:1")).toBe("foundation");
    await userEvent.click(screen.getByRole("button", { name: /Quick quiz/ }));
    await screen.findByRole("heading", { name: MCQ.prompt });
    expect(sent).toEqual({ mode: "quiz", topic_id: 10, subject_id: 1, include_higher: false });
  });

  it("explains when a topic has no questions", async () => {
    loggedInAs();
    server.use(http.get("*/api/topics/10", () => HttpResponse.json({ ...CELLS, question_count: 0 })));
    renderRoute("/revise/1/10");
    expect(await screen.findByText(/There aren't any questions for this topic yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Quick quiz/ })).not.toBeInTheDocument();
  });
});
