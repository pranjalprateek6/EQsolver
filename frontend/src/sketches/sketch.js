// p5 sketch factory. The canvas is created at the size the wrapper measures
// from its container so the internal resolution matches the displayed size
// 1:1 (otherwise CSS scaling makes only part of the visible box drawable).
// Keeps stroke history for undo, plus touch/stylus input, an adjustable brush
// and a baseline guide. The instance exposes a small imperative API.
export default function makeSketch(initialWidth, initialHeight) {
    return function sketch(p) {
        let strokes = [];
        let current = null;
        let weight = 4;
        let showBaseline = true;
        const BASELINE_Y = 0.72;

        const inCanvas = () =>
            p.mouseX >= 0 && p.mouseY >= 0 && p.mouseX <= p.width && p.mouseY <= p.height;

        const redraw = () => {
            p.background(255);
            if (showBaseline) {
                p.push();
                p.stroke(224);
                p.strokeWeight(1);
                p.line(0, p.height * BASELINE_Y, p.width, p.height * BASELINE_Y);
                p.pop();
            }
            p.stroke(0);
            p.noFill();
            for (const s of strokes) {
                p.strokeWeight(s.weight);
                if (s.points.length === 1) {
                    p.point(s.points[0].x, s.points[0].y);
                    continue;
                }
                for (let i = 1; i < s.points.length; i++) {
                    const a = s.points[i - 1];
                    const b = s.points[i];
                    p.line(a.x, a.y, b.x, b.y);
                }
            }
        };

        const startStroke = () => {
            current = { weight, points: [] };
            strokes.push(current);
        };

        const addPoint = () => {
            if (!current || !inCanvas()) return;
            current.points.push({ x: p.mouseX, y: p.mouseY });
            redraw();
        };

        const endStroke = () => {
            current = null;
        };

        p.setup = () => {
            p.createCanvas(initialWidth, initialHeight);
            redraw();
        };

        p.draw = () => {};

        p.mousePressed = () => {
            if (inCanvas()) startStroke();
        };
        p.mouseDragged = () => {
            addPoint();
        };
        p.mouseReleased = () => {
            endStroke();
        };

        // touch handlers mirror mouse; returning false stops the page from
        // scrolling while the user draws on the canvas
        p.touchStarted = () => {
            if (inCanvas()) {
                startStroke();
                addPoint();
                return false;
            }
        };
        p.touchMoved = () => {
            if (inCanvas()) {
                addPoint();
                return false;
            }
        };
        p.touchEnded = () => {
            endStroke();
        };

        // imperative API consumed by the React wrapper
        p.setStrokeWeight = (w) => {
            weight = w;
        };
        p.setBaseline = (on) => {
            showBaseline = on;
            redraw();
        };
        p.undo = () => {
            strokes.pop();
            redraw();
        };
        p.clearCanvas = () => {
            strokes = [];
            current = null;
            redraw();
        };
        p.isEmpty = () => strokes.length === 0;

        // keep the internal resolution matched to the displayed size, scaling
        // any existing strokes so the drawing is preserved across a resize
        p.resizeTo = (w, h) => {
            if (w <= 0 || h <= 0) return;
            const sx = w / p.width;
            const sy = h / p.height;
            for (const s of strokes) {
                for (const pt of s.points) {
                    pt.x *= sx;
                    pt.y *= sy;
                }
            }
            p.resizeCanvas(w, h);
            redraw();
        };

        p.exportImage = () => {
            // export without the baseline guide so it is not treated as ink
            const previous = showBaseline;
            showBaseline = false;
            redraw();
            const data = p.canvas.toDataURL();
            showBaseline = previous;
            redraw();
            return data;
        };
    };
}
