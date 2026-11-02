import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnswerResult } from "../../api/types";
import { CELLS, FILL, MATCH, MCQ, ORDER, SESSION, playState } from "../../test/fixtures";
import { renderRoute } from "../../test/render";
import { loggedInAs, server } from "../../test/server";

afterEach(() => vi.unstubAllGlobals());

const SUMMARY = {
  mode: "quiz" as const, status: "finished" as const, topic: { id: 10, name: "Cell biology" }, subject_id: 1,
  total: 2, answered: 2, correct: 1, accuracy: 0.5, xp_awarded: 0,
  results: [
    { position: 0, prompt: MCQ.prompt, correct: false },
    { position: 1, prompt: FILL.prompt, correct: true },
  ],
};

describe("quick quiz", () => {
  it("plays from the topic page to the results screen", async () => {
    loggedInAs();
    const sent: unknown[] = [];
    server.use(
      http.get("*/api/topics/10", () => HttpResponse.json(CELLS)),
      http.post("*/api/play", async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(playState(MCQ), { status: 201 });
      }),
      http.post(`*/api/play/${SESSION}/answer`, async ({ request }) => {
        const body = (await request.json()) as { position: number; response: unknown };
        sent.push(body);
        if (body.position === 0) {
          return HttpResponse.json<AnswerResult>({
            feedback: {
              position: 0, correct: false, partial: null,
              correct_answer: { option_id: "b", text: "Mitochondria" }, your_response: body.response as never,
              explanation: "Aerobic respiration happens in the mitochondria.",
              learn_more_url: "https://en.wikipedia.org/wiki/Cell_(biology)",
              review: { box: 1, due_on: "2026-11-03", days_until_due: 1 },
            },
            progress: { answered: 1, correct: 0, total: 2 }, next: FILL, summary: null,
          });
        }
        return HttpResponse.json<AnswerResult>({
          feedback: {
            position: 1, correct: true, partial: null, correct_answer: { text: "cellulose", also_accepted: [] },
            your_response: body.response as never, explanation: "Cellulose strengthens the cell wall.",
            learn_more_url: null, review: { box: 4, due_on: "2026-11-16", days_until_due: 14 },
          },
          progress: { answered: 2, correct: 1, total: 2 }, next: null, summary: SUMMARY,
        });
      }),
    );

    renderRoute("/revise/1/10");
    await userEvent.click(await screen.findByRole("button", { name: /Quick quiz/ }));

    // MCQ: answer wrong, see explanation + learn-more + when it comes back.
    expect(await screen.findByRole("heading", { name: MCQ.prompt })).toBeInTheDocument();
    const check = screen.getByRole("button", { name: "Check" });
    expect(check).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: /Ribosomes/ }));
    await userEvent.click(check);
    expect(await screen.findByRole("heading", { name: "Not quite" })).toBeInTheDocument();
    expect(screen.getByText(/Answer:/).closest("p")).toHaveTextContent("Answer: Mitochondria");
    expect(screen.getByText("Aerobic respiration happens in the mitochondria.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Learn more/ })).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("This question comes back tomorrow.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    // Fill-the-blank: Enter submits.
    await userEvent.type(await screen.findByLabelText("Your answer"), "cellulose{Enter}");
    expect(await screen.findByRole("heading", { name: "Correct!" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Learn more/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See results" }));

    expect(await screen.findByRole("heading", { name: "Nice going" })).toBeInTheDocument();
    expect(screen.getByText("50% correct")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Your answers" })).getAllByRole("listitem")).toHaveLength(2);

    expect(sent).toEqual([
      { mode: "quiz", topic_id: 10, subject_id: 1, include_higher: true },
      { position: 0, response: { option_id: "a" } },
      { position: 1, response: { text: "cellulose" } },
    ]);
  });

  it("orders items by tapping, and lets you take one back", async () => {
    loggedInAs();
    let sent: unknown;
    server.use(
      http.get(`*/api/play/${SESSION}`, () => HttpResponse.json(playState(ORDER, 1))),
      http.post(`*/api/play/${SESSION}/answer`, async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(
          { detail: "stop here", code: "x", field: null },
          { status: 409 },
        );
      }),
    );
    renderRoute(`/play/${SESSION}`);
    const check = await screen.findByRole("button", { name: "Check" });
    await userEvent.click(screen.getByRole("button", { name: "Second" }));
    await userEvent.click(screen.getByRole("button", { name: /1\. Second/ })); // take it back
    for (const label of ["First", "Second", "Third"]) {
      await userEvent.click(screen.getByRole("button", { name: label }));
    }
    expect(check).toBeEnabled();
    await userEvent.click(check);
    expect(sent).toEqual({ position: 0, response: { order: ["a", "b", "c"] } });
  });

  it("matches by tapping a term then a definition", async () => {
    loggedInAs();
    let sent: unknown;
    server.use(
      http.get(`*/api/play/${SESSION}`, () => HttpResponse.json(playState(MATCH, 1))),
      http.post(`*/api/play/${SESSION}/answer`, async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ detail: "stop", code: "x", field: null }, { status: 409 });
      }),
    );
    renderRoute(`/play/${SESSION}`);
    const check = await screen.findByRole("button", { name: "Check" });
    // First term is selected automatically.
    await userEvent.click(screen.getByRole("button", { name: /Charge \+1/ }));
    expect(check).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Charge −1/ }));
    await userEvent.click(check);
    expect(sent).toEqual({ position: 0, response: { pairs: { la: "ra", lb: "rb" } } });
  });

  it("can end a game early", async () => {
    loggedInAs();
    vi.stubGlobal("confirm", () => true);
    server.use(
      http.get(`*/api/play/${SESSION}`, () => HttpResponse.json(playState(MCQ, 10))),
      http.post(`*/api/play/${SESSION}/end`, () =>
        HttpResponse.json({ ...SUMMARY, status: "abandoned", answered: 0, correct: 0, accuracy: null, results: [] }),
      ),
    );
    renderRoute(`/play/${SESSION}`);
    await userEvent.click(await screen.findByRole("button", { name: "End game" }));
    expect(await screen.findByRole("heading", { name: "Quiz ended" })).toBeInTheDocument();
  });

  it("shows results when you reopen a finished game", async () => {
    loggedInAs();
    server.use(
      http.get(`*/api/play/${SESSION}`, () =>
        HttpResponse.json({ ...playState(MCQ), status: "finished", question: null, summary: SUMMARY }),
      ),
    );
    renderRoute(`/play/${SESSION}`);
    expect(await screen.findByRole("heading", { name: "Nice going" })).toBeInTheDocument();
  });
});
