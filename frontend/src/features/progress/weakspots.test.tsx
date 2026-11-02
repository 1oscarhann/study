import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { WeakSpot } from "../../api/types";
import { MCQ, playState } from "../../test/fixtures";
import { renderRoute } from "../../test/render";
import { loggedInAs, server } from "../../test/server";

const spot = (over: Partial<WeakSpot>): WeakSpot => ({
  topic_id: 10, subject_id: 1, name: "Cell biology", subject_name: "Biology", answered: 10, correct: 3,
  accuracy: 0.3, enough_data: true, last_played_at: null, ...over,
});

describe("weak spots", () => {
  it("lists topics worst first and revises one", async () => {
    loggedInAs();
    let sent: unknown;
    server.use(
      http.get("*/api/progress/weak-spots", () =>
        HttpResponse.json({
          window_days: 60, min_answers: 5,
          topics: [
            spot({}),
            spot({ topic_id: 20, subject_id: 3, name: "Atomic structure", subject_name: "Chemistry", correct: 9, accuracy: 0.9 }),
            spot({ topic_id: 30, subject_id: 4, name: "Weimar", subject_name: "History", answered: 3, correct: 2, accuracy: 0.667, enough_data: false }),
          ],
        }),
      ),
      http.post("*/api/play", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(playState(MCQ), { status: 201 });
      }),
    );
    renderRoute("/weak-spots");
    const ranked = await screen.findByText(/worst first/);
    const list = within(ranked.parentElement!).getByRole("list");
    const names = within(list).getAllByRole("listitem").map((li) => li.querySelector("p")?.textContent);
    expect(names).toEqual(["Cell biology", "Atomic structure"]);
    expect(screen.getByRole("heading", { name: /Not enough answers yet/ })).toBeInTheDocument();

    await userEvent.click(within(list).getAllByRole("button", { name: "Revise this" })[0]!);
    await screen.findByRole("heading", { name: MCQ.prompt });
    expect(sent).toEqual({ mode: "quiz", topic_id: 10, subject_id: 1, include_higher: true });
  });

  it("explains the empty state", async () => {
    loggedInAs();
    server.use(
      http.get("*/api/progress/weak-spots", () => HttpResponse.json({ window_days: 60, min_answers: 5, topics: [] })),
    );
    renderRoute("/weak-spots");
    expect(await screen.findByText(/Play a few quizzes/)).toBeInTheDocument();
  });
});
