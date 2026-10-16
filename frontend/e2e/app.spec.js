import { expect, test } from "@playwright/test";
import { drawGlyphs, GLYPHS } from "./draw";

const recognized = (page) => page.locator("#recognized-input");
const solution = (page) => page.locator(".result__solution");

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "EQsolver" })).toBeVisible();
});

async function drawOnePlusOne(page) {
  const canvas = page.getByRole("region", { name: "Drawing board" }).locator(".drawing__canvas");
  await drawGlyphs(page, canvas, [GLYPHS[1], GLYPHS["+"], GLYPHS[1]]);
  await page.getByRole("button", { name: "Evaluate" }).click();
}

test("draw an equation and evaluate it", async ({ page }) => {
  await drawOnePlusOne(page);

  await expect(recognized(page)).toHaveValue("1+1");
  await expect(page.locator(".glyph")).toHaveCount(3);
  await expect(solution(page)).toContainText("2");
});

test("tap a glyph and correct it from the picker", async ({ page }) => {
  await drawOnePlusOne(page);
  await expect(recognized(page)).toHaveValue("1+1");

  await page.getByRole("button", { name: /^Character 1: read as 1/ }).click();
  const picker = page.getByRole("group", { name: "Change character 1" });
  await expect(picker).toBeVisible();
  await picker.getByRole("button", { name: "7", exact: true }).click();

  // the layout is re-read with the corrected glyph and solved again
  await expect(recognized(page)).toHaveValue("7+1");
  await expect(solution(page)).toContainText("8");
  await expect(page.getByRole("button", { name: /^Character 1: read as 7, 100% sure/ })).toBeVisible();
});

test("solve an example and show the steps", async ({ page }) => {
  await page.locator(".examples__chip", { hasText: "x^2-5x+6=0" }).first().click();

  await expect(recognized(page)).toHaveValue("x^2-5x+6=0");
  await expect(solution(page)).toContainText("2");
  await expect(solution(page)).toContainText("3");

  const steps = page.locator("details.steps");
  await steps.locator("summary", { hasText: "Show steps" }).click();
  await expect(steps).toHaveAttribute("open", "");
  await expect(steps.locator(".steps__item").first()).toBeVisible();
  await expect(steps.locator(".steps__item")).toHaveCount(4);
  await expect(steps.getByText("Factor", { exact: true })).toBeVisible();
});

test("open a share link", async ({ page }) => {
  await page.goto(`/#q=${encodeURIComponent("2x+3=11")}`);

  await expect(recognized(page)).toHaveValue("2x+3=11");
  await expect(solution(page)).toContainText("4");
  await expect(page.getByRole("button", { name: "Copy link" })).toBeVisible();
});

test("check my work finds the wrong line", async ({ page }) => {
  await page.getByRole("button", { name: "Check my work" }).click();
  await page.getByRole("button", { name: "Type", exact: true }).click();
  await page.locator("#typed-work").fill("2x+3=11\n2x=14\nx=7");
  await page.getByRole("button", { name: "Check", exact: true }).click();

  await expect(page.locator(".check__summary")).toHaveText("Line 2 does not follow from line 1.");
  const lines = page.locator(".check__line");
  await expect(lines).toHaveCount(3);
  await expect(lines.nth(1)).toHaveClass(/check__line--bad/);
  await expect(lines.nth(1)).toHaveClass(/check__line--first/);
  await expect(lines.nth(1).locator(".check__hint")).toBeVisible();
});
