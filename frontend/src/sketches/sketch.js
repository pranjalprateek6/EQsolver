// p5 sketch factory. The canvas is created at the size the wrapper measures
// from its container so the internal resolution matches the displayed size
// 1:1 (otherwise CSS scaling makes only part of the visible box drawable).
// Keeps stroke history for undo, plus touch/stylus input, an adjustable brush
// and a baseline guide. The instance exposes a small imperative API.
//
// While drawing, only the newest segment is painted; the full history is
// repainted only on undo/redo/clear/resize, so long equations stay smooth.
export default function makeSketch(initialWidth, initialHeight) {
    return function sketch(p) {
        let strokes = [];
        // strokes taken back by undo, restored by redo; cleared by new ink
        let undone = [];
        // the drawing as it was before Clear, so Undo can bring it back
        let cleared = null;
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
            undone = [];
            cleared = null;
        };

        const addPoint = () => {
            if (!current || !inCanvas()) return;
            const point = { x: p.mouseX, y: p.mouseY };
            const prev = current.points[current.points.length - 1];
            current.points.push(point);
            // paint just the new piece instead of repainting every stroke
            p.stroke(0);
            p.strokeWeight(current.weight);
            if (prev) p.line(prev.x, prev.y, point.x, point.y);
            else p.point(point.x, point.y);
        };

        const endStroke = () => {
            // a click outside the canvas leaves an empty stroke; drop it
            if (current && current.points.length === 0) strokes.pop();
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
            if (strokes.length === 0 && cleared) {
                strokes = cleared;
                cleared = null;
                redraw();
                return;
            }
            if (strokes.length === 0) return;
            undone.push(strokes.pop());
            redraw();
        };
        p.redo = () => {
            if (undone.length === 0) return;
            strokes.push(undone.pop());
            redraw();
        };
        p.clearCanvas = () => {
            // clearing is undoable: Undo brings the whole drawing back
            if (strokes.length) cleared = strokes;
            undone = [];
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
            // export at 1x: on a high-density screen the backing canvas has
            // 4-9x the pixels, which only makes the upload bigger and slower
            const out = document.createElement('canvas');
            out.width = p.width;
            out.height = p.height;
            out.getContext('2d').drawImage(p.canvas, 0, 0, p.width, p.height);
            const data = out.toDataURL('image/png');
            showBaseline = previous;
            redraw();
            return data;
        };
    };
}
