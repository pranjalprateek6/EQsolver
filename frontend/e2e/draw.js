// Draw on a .drawing__canvas with real pointer events (Playwright's mouse
// produces pointerdown/move/up of pointerType "mouse"). Strokes are lists of
// [x, y] points in glyph units: each glyph is one unit wide and tall, its top
// at y = 0, and glyph i starts at x = i * 1.4.

export async function drawGlyphs(page, canvas, glyphs, { size = 70, left = 60, top } = {}) {
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  const y0 = top ?? box.height * 0.72 - size; // sit on the guide line
  const at = ([x, y]) => [box.x + left + x * size, box.y + y0 + y * size];
  for (const [i, strokes] of glyphs.entries()) {
    for (const points of strokes) {
      const shifted = points.map(([x, y]) => at([x + i * 1.4, y]));
      await page.mouse.move(...shifted[0]);
      await page.mouse.down();
      for (const point of shifted.slice(1)) await page.mouse.move(...point, { steps: 8 });
      await page.mouse.up();
    }
  }
}

// a few printed glyphs that the model reads reliably
export const GLYPHS = {
  1: [[[0.5, 0], [0.5, 1]]],
  "+": [
    [[0.1, 0.5], [0.9, 0.5]],
    [[0.5, 0.1], [0.5, 0.9]],
  ],
  "=": [
    [[0.1, 0.35], [0.9, 0.35]],
    [[0.1, 0.7], [0.9, 0.7]],
  ],
  7: [[[0.1, 0], [0.9, 0], [0.35, 1]]],
};
