import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AutomationForm } from "./AutomationForm";

describe("AutomationForm", () => {
  it("asks for required fields before saving", () => {
    const onSubmit = vi.fn();
    render(<AutomationForm submitLabel="Save automation" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: "Save automation" }));

    expect(screen.getByText("Enter a name.")).toBeInTheDocument();
    expect(screen.getByText("Enter an executable.")).toBeInTheDocument();
    expect(screen.getByText("Enter a working directory.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
