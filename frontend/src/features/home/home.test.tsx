import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Home } from "../../api/types";
import { EMPTY_HOME, MCQ, SUBJECTS, playState } from "../../test/fixtures";
import { renderRoute } from "../../test/render";
import { loggedInAs, server } from "../../test/server";

const BUSY_HOME: Home = {
  ...EMPTY_HOME,
  due_reviews: { today: 3, this_week: 8 },
  recent_topics: [
    { topic_id: 10, subject_id: 1, name: "Cell biology", subject_name: "Biology", accuracy: 0.4, last_played_at: "2026-11-02T10:00:00Z" },
  ],
  weakest_topic: {
    topic_id: 10, subject_id: 1, name: "Cell biology", subject_name: "Biology", answered: 10, correct: 4,
    accuracy: 0.4, enough_data: true, last_played_at: "2026-11-02T10:00:00Z",
  },
  exams: [{ id: 5, subject_id: 1, subject_name: "Biology", label: "Paper 1", exam_date: "2027-05-14", days_left: 193 }],
};

describe("home", () => {
  it("nudges a new student to their first quiz", async () => {
    loggedInAs();
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Start your first quiz" })).toBeInTheDocument();
    expect(screen.getByText(/All caught up/)).toBeInTheDocument();
  });

  it("shows due reviews, weakest topic, recent topics and exams", async () => {
    loggedInAs();
    server.use(http.get("*/api/home", () => HttpResponse.json(BUSY_HOME)));
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "3 questions to review" })).toBeInTheDocument();
    expect(screen.getByText("Your weakest topic")).toBeInTheDocument();
    expect(screen.getByText("Biology · Paper 1")).toBeInTheDocument();
    expect(screen.getByText("193")).toBeInTheDocument();
  });

  it("starts a review from the review card", async () => {
    loggedInAs();
    let sent: unknown;
    server.use(
      http.get("*/api/home", () => HttpResponse.json(BUSY_HOME)),
      http.post("*/api/play", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ...playState(MCQ), mode: "review", topic: null }, { status: 201 });
      }),
    );
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Review" }));
    expect(await screen.findByText(/Review · Cell biology/)).toBeInTheDocument();
    expect(sent).toEqual({ mode: "review" });
  });

  it("revises the weakest topic in one tap", async () => {
    loggedInAs();
    let sent: unknown;
    server.use(
      http.get("*/api/home", () => HttpResponse.json(BUSY_HOME)),
      http.post("*/api/play", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(playState(MCQ), { status: 201 });
      }),
    );
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Revise weakest topic" }));
    await screen.findByRole("heading", { name: MCQ.prompt });
    expect(sent).toEqual({ mode: "quiz", topic_id: 10, subject_id: 1, include_higher: true });
  });

  it("adds and removes an exam", async () => {
    loggedInAs();
    let added: unknown;
    let deleted = false;
    server.use(
      http.get("*/api/home", () => HttpResponse.json(BUSY_HOME)),
      http.get("*/api/subjects", () => HttpResponse.json({ subjects: SUBJECTS })),
      http.post("*/api/exams", async ({ request }) => {
        added = await request.json();
        return HttpResponse.json({ id: 6, subject_id: 2, subject_name: "Mathematics", label: null, exam_date: "2027-05-21", days_left: 200 }, { status: 201 });
      }),
      http.delete("*/api/exams/5", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "+ Add exam" }));
    await userEvent.selectOptions(screen.getByLabelText("Subject"), "2");
    await userEvent.type(screen.getByLabelText("Exam date"), "2027-05-21");
    await userEvent.click(screen.getByRole("button", { name: "Add exam" }));
    expect(added).toEqual({ subject_id: 2, exam_date: "2027-05-21", label: null });

    await userEvent.click(screen.getByRole("button", { name: "Remove Biology exam" }));
    expect(deleted).toBe(true);
  });
});
