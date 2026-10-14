import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ResultPanel, { formatSolution } from "./ResultPanel";

describe("formatSolution", () => {
  it("unwraps a root list", () => {
    expect(formatSolution("[-2, 2]")).toBe("-2, 2");
  });

  it("does not invent a variable name", () => {
    expect(formatSolution("[3]")).not.toMatch(/x =/);
  });

  it("handles empty and identity results", () => {
    expect(formatSolution("[]")).toBe("No solution");
    expect(formatSolution("all values")).toBe("True for every value");
  });

  it("passes numbers through", () => {
    expect(formatSolution("11")).toBe("11");
  });
});

describe("ResultPanel", () => {
  const props = {
    recognized: "y**2=9",
    onRecognizedChange: vi.fn(),
    onSolve: vi.fn(),
    solving: false,
    latex: "",
    solution: "[-3, 3]",
    solutionLatex: "",
    solved: true,
  };

  it("labels the editable equation", () => {
    render(<ResultPanel {...props} />);
    expect(screen.getByLabelText(/recognized equation/i)).toHaveValue("y**2=9");
  });

  it("shows a plain solution when there is no LaTeX", () => {
    render(<ResultPanel {...props} />);
    expect(screen.getByText("-3, 3")).toBeInTheDocument();
  });

  it("says when it could not solve", () => {
    render(<ResultPanel {...props} solved={false} solution="" />);
    expect(screen.getByText(/could not solve/i)).toBeInTheDocument();
  });
});
