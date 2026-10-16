import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import App from "./App";

describe("App", () => {
  it("renders the heading and canvas controls", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /eqsolver/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /evaluate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /undo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
  });

  it("switches to check my work and back, keeping the solver", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /check my work/i }));
    expect(screen.getByRole("button", { name: /check my work/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Check" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /ruled drawing area/i })).toBeInTheDocument();
    // the solver is hidden, not thrown away
    expect(screen.queryByRole("button", { name: /evaluate/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Solve" }));
    expect(screen.getByRole("button", { name: /evaluate/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check" })).not.toBeInTheDocument();
  });
});
