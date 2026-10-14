import { afterEach, describe, expect, it, vi } from "vitest";
import { postJson } from "./api";

function mockFetch(response) {
  globalThis.fetch = vi.fn().mockResolvedValue(response);
}

function jsonResponse(status, body) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) };
}

describe("postJson", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the parsed body on success", async () => {
    mockFetch(jsonResponse(200, { solution: "11" }));
    await expect(postJson("/solve", { expression: "8+3" })).resolves.toEqual({ solution: "11" });
  });

  it("uses the server's error message, in sentence case", async () => {
    mockFetch(jsonResponse(422, { error: "could not solve that expression" }));
    await expect(postJson("/solve", {})).rejects.toThrow("Could not solve that expression.");
  });

  it("explains an HTML error page from a proxy instead of a JSON parse error", async () => {
    mockFetch({ ok: false, status: 502, json: () => Promise.reject(new SyntaxError("Unexpected token <")) });
    await expect(postJson("/predict", {})).rejects.toThrow(/restarting/i);
  });

  it("explains rate limiting", async () => {
    mockFetch({ ok: false, status: 429, json: () => Promise.reject(new SyntaxError("x")) });
    await expect(postJson("/solve", {})).rejects.toThrow(/too many requests/i);
  });

  it("reports a network failure plainly", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(postJson("/solve", {})).rejects.toThrow(/could not reach the server/i);
  });
});
