import { afterEach, describe, expect, it, vi } from "vitest";
import { clearHistory, expressionFromLink, loadHistory, remember, shareLink } from "./history";

describe("history", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    window.location.hash = "";
  });

  it("keeps the newest first without duplicates", () => {
    remember("x^2=4");
    remember("8+3");
    remember("x^2=4");
    expect(loadHistory().map((i) => i.expression)).toEqual(["x^2=4", "8+3"]);
  });

  it("keeps at most eight", () => {
    for (let i = 0; i < 12; i++) remember(`${i}+1`);
    const items = loadHistory();
    expect(items).toHaveLength(8);
    expect(items[0].expression).toBe("11+1");
  });

  it("ignores blank expressions", () => {
    remember("   ");
    expect(loadHistory()).toEqual([]);
  });

  it("survives corrupt or unavailable storage", () => {
    localStorage.setItem("eqsolver.history", "{not json");
    expect(loadHistory()).toEqual([]);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(remember("1+1", [])).toEqual([{ expression: "1+1" }]);
  });

  it("clears", () => {
    remember("1+1");
    expect(clearHistory()).toEqual([]);
    expect(loadHistory()).toEqual([]);
  });
});

describe("share links", () => {
  afterEach(() => {
    window.location.hash = "";
  });

  it("round-trips an equation through the fragment", () => {
    const link = shareLink("(x+1)/2=4");
    expect(link).toContain("#q=");
    window.location.hash = new URL(link).hash;
    expect(expressionFromLink()).toBe("(x+1)/2=4");
  });

  it("returns nothing without a q fragment", () => {
    window.location.hash = "#other";
    expect(expressionFromLink()).toBe("");
  });

  it("caps the length", () => {
    window.location.hash = `#q=${"1+".repeat(400)}1`;
    expect(expressionFromLink().length).toBe(300);
  });
});
