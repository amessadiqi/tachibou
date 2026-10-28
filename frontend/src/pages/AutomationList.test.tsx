import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AutomationList } from "./AutomationList";

const nightly = {
  id: "auto-1",
  name: "Nightly report",
  description: "Builds the nightly report.",
  owner: null,
  version: null,
  executable: "/usr/bin/python3",
  arguments: [],
  working_directory: "/work",
  entry_point: null,
  created_at: "2026-10-25T00:00:00Z",
  updated_at: "2026-10-25T00:00:00Z",
  configuration_errors: ["The executable could not be found."],
  file_references: [],
  running: false,
  latest_execution: {
    id: "exec-9",
    status: "failed" as const,
    trigger_type: "manual" as const,
    started_at: "2026-10-25T01:00:00Z",
    ended_at: "2026-10-25T01:00:02Z",
    exit_code: 1,
  },
};

describe("AutomationList", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows an empty state when nothing is registered", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
    );

    render(
      <MemoryRouter>
        <AutomationList />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/No automations yet/i),
    ).toBeInTheDocument();
  });

  it("lists automations and searches by name", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [nightly],
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <AutomationList />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Nightly report")).toBeInTheDocument();
    expect(screen.getByText("Check the configuration")).toBeInTheDocument();
    expect(screen.getByText(/Last result: Failed/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search by name"), { target: { value: "night" } });

    expect(await screen.findByText("Nightly report")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/automations?search=night",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("starts a run once and opens the execution", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      if (init?.method === "POST" && String(input).endsWith("/executions")) {
        return {
          ok: true,
          json: async () => ({ id: "exec-1", automation_id: "auto-1", status: "running" }),
        };
      }
      return { ok: true, json: async () => [{ ...nightly, latest_execution: null }] };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<AutomationList />} />
          <Route path="/automations/:automationId/executions/:executionId" element={<p>Execution open</p>} />
        </Routes>
      </MemoryRouter>,
    );

    const button = await screen.findByRole("button", { name: "Run Nightly report" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(await screen.findByText("Execution open")).toBeInTheDocument();
    const posts = fetchMock.mock.calls.filter((call) => call[1]?.method === "POST");
    expect(posts).toHaveLength(1);
  });
});
