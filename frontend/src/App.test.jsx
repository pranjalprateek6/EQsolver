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
  it("renders the heading and canvas controls", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /eqsolver/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /evaluate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /undo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
  });
});
