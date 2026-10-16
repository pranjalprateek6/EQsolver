import { forwardRef, useImperativeHandle } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import CheckWork from "./CheckWork";

// jsdom cannot paint a canvas, so stand in a drawing that is never empty
vi.mock("./DrawingCanvas", () => ({
  default: forwardRef(function FakeCanvas(props, ref) {
    useImperativeHandle(ref, () => ({
      isEmpty: () => false,
      exportImage: () => "data:image/png;base64,AAAA",
      clearCanvas: () => {},
      undo: () => {},
      setStrokeWeight: () => {},
    }));
    return <div data-testid="canvas" data-rules={props.rules} />;
  }),
}));

function jsonResponse(body, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) };
}

// answer each POST from a queue, recording what was sent
function mockServer(...bodies) {
  const calls = [];
  globalThis.fetch = vi.fn((url, init) => {
    calls.push({ path: new URL(url, "http://x").pathname, body: JSON.parse(init.body) });
    return Promise.resolve(jsonResponse(bodies.shift()));
  });
  return calls;
}

const WRONG = {
  lines: [
    { text: "2x+3=11", latex: "2 x + 3 = 11", ok: true, reason: "" },
    {
      text: "2x=11+3",
      latex: "2 x = 11 + 3",
      ok: false,
      reason: "check the sign when you moved 3 across the =: it should become -3 on the other side",
    },
    { text: "x=8", latex: "x = 8", ok: false, reason: "this line has different solutions than the one before" },
  ],
  first_error: 1,
  finished: false,
};

const RIGHT = {
  lines: [
    { text: "2x+3=11", latex: "2 x + 3 = 11", ok: true, reason: "" },
    { text: "2x=8", latex: "2 x = 8", ok: true, reason: "" },
    { text: "x=4", latex: "x = 4", ok: true, reason: "" },
  ],
  first_error: null,
  finished: true,
};

function typeWorking(text) {
  fireEvent.click(screen.getByRole("button", { name: "Type" }));
  fireEvent.change(screen.getByLabelText(/one equation per line/i), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Check" }));
}

describe("CheckWork", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("draws on a ruled surface", () => {
    render(<CheckWork />);
    expect(Number(screen.getByTestId("canvas").dataset.rules)).toBeGreaterThan(1);
  });

  it("sends typed lines without blanks and flags the first wrong line with its hint", async () => {
    const calls = mockServer(WRONG);
    render(<CheckWork />);
    typeWorking("2x+3=11\n\n 2x=11+3 \nx=8\n");

    expect(await screen.findByText(/line 2 does not follow from line 1/i)).toBeInTheDocument();
    expect(calls[0]).toEqual({ path: "/check", body: { lines: ["2x+3=11", "2x=11+3", "x=8"] } });

    const items = screen.getAllByRole("listitem");
    expect(within(items[1]).getByRole("img", { name: /changes the solutions/i })).toBeInTheDocument();
    expect(within(items[1]).getByText(/check the sign when you moved 3/i)).toBeInTheDocument();
    expect(items[1]).toHaveClass("check__line--first");
    // only the first mistake gets a hint
    expect(within(items[2]).queryByText(/different solutions/i)).not.toBeInTheDocument();
  });

  it("never shows the answer unless asked", async () => {
    const calls = mockServer(WRONG, { ...WRONG, answer_latex: "x = 4" });
    render(<CheckWork />);
    typeWorking("2x+3=11\n2x=11+3\nx=8");
    await screen.findByText(/line 2 does not follow/i);
    expect(screen.queryByText(/answer to line 1/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /show the answer/i }));
    expect(await screen.findByText(/answer to line 1/i)).toBeInTheDocument();
    expect(calls[1].body).toEqual({ lines: ["2x+3=11", "2x=11+3", "x=8"], reveal: true });
  });

  it("congratulates finished, correct working", async () => {
    mockServer(RIGHT);
    render(<CheckWork />);
    typeWorking("2x+3=11\n2x=8\nx=4");
    expect(await screen.findByText(/every step checks out, and you reached/i)).toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: /correct step/i })).toHaveLength(2);
  });

  it("checks a handwritten page and fixes one line's reading by tapping a glyph", async () => {
    const glyphs = [
      { char: "2", confidence: 0.9, image: "", alternatives: [], x: 0, y: 0, w: 10, h: 20 },
      { char: "x", confidence: 0.9, image: "", alternatives: [], x: 12, y: 0, w: 10, h: 20 },
      { char: "=", confidence: 0.9, image: "", alternatives: [], x: 24, y: 5, w: 10, h: 8 },
      { char: "9", confidence: 0.4, image: "", alternatives: [], x: 36, y: 0, w: 10, h: 20 },
    ];
    const handwritten = {
      lines: [
        { ...RIGHT.lines[0], characters: glyphs },
        { text: "2*x=9", latex: "2 x = 9", ok: false, reason: "this line has different solutions than the one before", characters: glyphs },
      ],
      first_error: 1,
      finished: false,
    };
    const calls = mockServer(
      handwritten,
      { recognized: "2*x=8" },
      { lines: [RIGHT.lines[0], { ...RIGHT.lines[1], text: "2*x=8" }], first_error: null, finished: false }
    );
    render(<CheckWork />);
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    await screen.findByText(/line 2 does not follow/i);
    expect(calls[0].body).toEqual({ image: "AAAA" });

    const line2 = screen.getAllByRole("listitem")[1];
    fireEvent.click(within(line2).getByRole("button", { name: /fix reading/i }));
    fireEvent.click(within(line2).getByRole("button", { name: /character 4/i }));
    fireEvent.click(within(line2).getByRole("button", { name: "8" }));

    expect(await screen.findByText(/every step so far checks out/i)).toBeInTheDocument();
    expect(calls[1].path).toBe("/rebuild");
    expect(calls[1].body.characters.map((c) => c.char)).toEqual(["2", "x", "=", "8"]);
    expect(calls[2]).toEqual({ path: "/check", body: { lines: ["2x+3=11", "2*x=8"] } });
    // the glyphs survive the typed re-check, so the strip stays open for more fixes
    expect(
      within(screen.getAllByRole("listitem")[1]).getByRole("button", { name: "Done" })
    ).toBeInTheDocument();
  });

  it("explains an empty submission without calling the server", () => {
    globalThis.fetch = vi.fn();
    render(<CheckWork />);
    typeWorking("   \n ");
    expect(screen.getByRole("alert")).toHaveTextContent(/type your working first/i);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("shows server errors", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ error: "too many lines (max 12)" }, 400));
    render(<CheckWork />);
    typeWorking("x=1\nx=1");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/too many lines/i));
  });
});
