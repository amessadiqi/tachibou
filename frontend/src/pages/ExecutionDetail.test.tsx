import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExecutionDetail } from "./ExecutionDetail";

const execution = {
  id: "exec-1",
  automation_id: "auto-1",
  schedule_id: null,
  trigger_type: "manual",
  status: "failed",
  started_at: "2026-10-27T12:00:00Z",
  ended_at: "2026-10-27T12:00:01Z",
  duration_ms: 1000,
  exit_code: 3,
  stdout_path: "executions/exec-1/stdout.log",
  stderr_path: "executions/exec-1/stderr.log",
  error_message: "The executable could not be found.",
};

describe("ExecutionDetail", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the result and loads output in chunks", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/output?")) {
        const offset = new URL(url, "http://localhost").searchParams.get("offset");
        if (offset === "0") {
          return {
            ok: true,
            json: async () => ({
              stream: url.includes("stream=stderr") ? "stderr" : "stdout",
              offset: 0,
              next_offset: 4,
              size: 8,
              eof: false,
              content: url.includes("stream=stderr") ? "boom" : "abcd",
            }),
          };
        }
        return {
          ok: true,
          json: async () => ({
            stream: "stdout",
            offset: 4,
            next_offset: 8,
            size: 8,
            eof: true,
            content: "efgh",
          }),
        };
      }
      return { ok: true, json: async () => execution };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/automations/auto-1/executions/exec-1"]}>
        <Routes>
          <Route path="/automations/:automationId/executions/:executionId" element={<ExecutionDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Failed" })).toBeInTheDocument();
    expect(screen.getByText("The executable could not be found.")).toBeInTheDocument();
    expect(await screen.findByText("abcd")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("limit=32768"))).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Show more standard output" }));
    expect(await screen.findByText("abcdefgh")).toBeInTheDocument();
  });

  it("keeps looking when the execution record is not ready yet", async () => {
    let executionReads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/output?")) {
          return {
            ok: true,
            json: async () => ({
              stream: url.includes("stream=stderr") ? "stderr" : "stdout",
              offset: 0,
              next_offset: 5,
              size: 5,
              eof: true,
              content: "hello",
            }),
          };
        }
        executionReads += 1;
        if (executionReads === 1) {
          return {
            ok: false,
            json: async () => ({ message: "This execution could not be found." }),
          };
        }
        return {
          ok: true,
          json: async () => ({ ...execution, status: "succeeded", exit_code: 0, error_message: null }),
        };
      }),
    );

    render(
      <MemoryRouter initialEntries={["/automations/auto-1/executions/exec-1"]}>
        <Routes>
          <Route path="/automations/:automationId/executions/:executionId" element={<ExecutionDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Succeeded" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect((await screen.findAllByText("hello")).length).toBeGreaterThan(0);
  });
});