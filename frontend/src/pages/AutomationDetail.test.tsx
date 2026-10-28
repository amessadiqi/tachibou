import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { AutomationDetail } from "./AutomationDetail";

const automation = {
  id: "auto-1",
  name: "Nightly report",
  description: null,
  owner: null,
  version: null,
  executable: "/usr/bin/python3",
  arguments: ["job.py"],
  working_directory: "/work",
  entry_point: "/work/job.py",
  created_at: "2026-10-25T12:00:00Z",
  updated_at: "2026-10-25T12:00:00Z",
  configuration_errors: [],
  file_references: [],
};

describe("AutomationDetail", () => {
  it("asks for confirmation before unregistering", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return { ok: true };
      }
      if (String(input).includes("/executions")) {
        return { ok: true, json: async () => ({ items: [], total: 0, limit: 20, offset: 0 }) };
      }
      return {
        ok: true,
        json: async () => ({ ...automation, running: false, latest_execution: null }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/automations/auto-1"]}>
        <Routes>
          <Route path="/automations/:automationId" element={<AutomationDetail />} />
          <Route path="/" element={<p>Back home</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Nightly report" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Unregister" }));
    expect(screen.getByText(/project files stay where they are/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/automations/auto-1",
      expect.objectContaining({ method: "DELETE" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Unregister automation" }));
    expect(await screen.findByText("Back home")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/automations/auto-1", { method: "DELETE" });
  });
});
