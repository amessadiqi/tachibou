import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
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

    fireEvent.change(screen.getByLabelText("Search by name"), { target: { value: "night" } });

    expect(await screen.findByText("Nightly report")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/automations?search=night",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});
