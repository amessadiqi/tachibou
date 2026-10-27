import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockFetch(healthOk: boolean, healthRejects = false) {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (healthRejects) {
      throw new Error("offline");
    }
    if (url.startsWith("/api/automations")) {
      return { ok: true, json: async () => [] };
    }
    return {
      ok: healthOk,
      json: async () => ({
        status: "ok",
        name: "Tâchibou",
        version: "0.1.0",
        database: "ok",
      }),
    };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App", () => {
  it("shows the service status returned by the API", async () => {
    const fetchMock = mockFetch(true);

    render(<App />);

    expect(await screen.findByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText("Reachable")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows a clear message when the API is unreachable", async () => {
    mockFetch(false, true);

    render(<App />);

    expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent(/cannot reach/i);
  });

  it("reports an unexpected API response", async () => {
    mockFetch(false);

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/unexpected response/i);
  });
});
