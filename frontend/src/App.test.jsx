import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// p5 needs a real canvas; mock it out in jsdom
vi.mock("p5", () => ({
  default: class MockP5 {
    constructor() {}
    remove() {}
  },
}));

import App from "./App";

describe("App", () => {
  it("renders the drawing prompt and controls", () => {
    render(<App />);
    expect(screen.getByText(/draw the equation below/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /evaluate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
  });
});
