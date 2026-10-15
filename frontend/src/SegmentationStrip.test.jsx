import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import SegmentationStrip from "./SegmentationStrip";

const characters = [
  { char: "2", confidence: 0.99, image: "", alternatives: [{ char: "2", confidence: 0.99 }] },
  {
    char: "x",
    confidence: 0.55,
    image: "",
    alternatives: [
      { char: "x", confidence: 0.55 },
      { char: "×", confidence: 0.45 },
    ],
  },
];

describe("SegmentationStrip", () => {
  it("offers the model's other guesses when a tile is tapped", () => {
    render(<SegmentationStrip characters={characters} onCorrect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /character 2/i }));
    expect(screen.getByText(/did you mean/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /×\s*45%/ })).toBeInTheDocument();
  });

  it("reports the picked symbol and closes", () => {
    const onCorrect = vi.fn();
    render(<SegmentationStrip characters={characters} onCorrect={onCorrect} />);
    fireEvent.click(screen.getByRole("button", { name: /character 2/i }));
    fireEvent.click(screen.getByRole("button", { name: /×\s*45%/ }));
    expect(onCorrect).toHaveBeenCalledWith(1, "×");
    expect(screen.queryByText(/did you mean/i)).not.toBeInTheDocument();
  });

  it("lets any symbol be picked", () => {
    const onCorrect = vi.fn();
    render(<SegmentationStrip characters={characters} onCorrect={onCorrect} />);
    fireEvent.click(screen.getByRole("button", { name: /character 1/i }));
    fireEvent.click(screen.getByRole("button", { name: "7" }));
    expect(onCorrect).toHaveBeenCalledWith(0, "7");
  });

  it("does nothing when the same symbol is picked again", () => {
    const onCorrect = vi.fn();
    render(<SegmentationStrip characters={characters} onCorrect={onCorrect} />);
    fireEvent.click(screen.getByRole("button", { name: /character 1/i }));
    fireEvent.click(screen.getByRole("button", { name: "2", pressed: true }));
    expect(onCorrect).not.toHaveBeenCalled();
  });
});
