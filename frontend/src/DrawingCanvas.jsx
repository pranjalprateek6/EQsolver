import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";

// Height / width of the drawing surface. Narrow screens get a taller surface
// so there is room to write with a finger.
const ASPECT = 0.46;
const NARROW_ASPECT = 0.7;
const NARROW_WIDTH = 600;
// faint guide line, as a fraction of the height (not part of the export)
const BASELINE_Y = 0.72;

// keyed to the screen, not the canvas: on desktop the two-column layout
// makes the canvas narrow too, but there is no finger to make room for
const heightFor = (width) =>
  Math.round(width * (window.innerWidth < NARROW_WIDTH ? NARROW_ASPECT : ASPECT));

// A pen's pressure scales the line between these multiples of the brush
// size; mice and fingers report no real pressure and draw at 1x.
const MIN_PRESSURE_SCALE = 0.55;
const MAX_PRESSURE_SCALE = 1.45;

function pressureScale(event) {
  if (event.pointerType !== "pen" || !event.pressure) return 1;
  return MIN_PRESSURE_SCALE + (MAX_PRESSURE_SCALE - MIN_PRESSURE_SCALE) * event.pressure;
}

// Draw one stroke as a smooth curve: quadratic segments through the
// midpoints between samples, which removes the polyline "kinks".
function drawStroke(ctx, stroke, from = 0) {
  const pts = stroke.points;
  if (pts.length === 0) return;
  ctx.strokeStyle = "#000";
  ctx.fillStyle = "#000";
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (pts.length === 1) {
    ctx.beginPath();
    ctx.arc(pts[0].x, pts[0].y, (stroke.weight * pts[0].p) / 2, 0, Math.PI * 2);
    ctx.fill();
    return;
  }
  for (let i = Math.max(1, from); i < pts.length; i++) {
    const a = pts[i - 1];
    const b = pts[i];
    const prev = i >= 2 ? pts[i - 2] : a;
    const start = { x: (prev.x + a.x) / 2, y: (prev.y + a.y) / 2 };
    const end = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    ctx.lineWidth = stroke.weight * (a.p + b.p) / 2;
    ctx.beginPath();
    ctx.moveTo(i === 1 ? a.x : start.x, i === 1 ? a.y : start.y);
    ctx.quadraticCurveTo(a.x, a.y, end.x, end.y);
    if (i === pts.length - 1) ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
}

// The drawing surface: Pointer Events (mouse, touch and pen alike), pen
// pressure, smoothed strokes, coalesced events so fast pens do not lose
// points, and palm rejection (touches are ignored while a pen is down).
// Only the newest segment is painted while drawing; the full history is
// repainted on undo, redo, clear and resize.
//
// The parent drives it through a ref: undo, redo, clearCanvas, isEmpty,
// setStrokeWeight, exportImage and getStrokes.
const DrawingCanvas = forwardRef(function DrawingCanvas({ onStrokeEnd }, ref) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const state = useRef({
    strokes: [],
    undone: [],
    cleared: null, // the drawing before Clear, so Undo can bring it back
    current: null,
    pointerId: null,
    penActive: false,
    weight: 4,
    width: 0,
    height: 0,
  });

  const context = () => canvasRef.current?.getContext("2d");

  const repaint = useCallback(() => {
    const ctx = context();
    const s = state.current;
    if (!ctx) return;
    ctx.clearRect(0, 0, s.width, s.height);
    for (const stroke of s.strokes) drawStroke(ctx, stroke);
  }, []);

  // size the backing store to the displayed size times the pixel ratio, so
  // ink is crisp on high-density screens; strokes are kept in CSS pixels
  const resize = useCallback(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    const width = container.clientWidth || 550;
    const height = heightFor(width);
    const s = state.current;
    if (Math.abs(width - s.width) <= 1 && s.height) return;
    if (s.width) {
      const sx = width / s.width;
      const sy = height / s.height;
      for (const stroke of s.strokes) {
        for (const pt of stroke.points) {
          pt.x *= sx;
          pt.y *= sy;
        }
      }
    }
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.height = `${height}px`;
    s.width = width;
    s.height = height;
    const ctx = context();
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    repaint();
  }, [repaint]);

  useEffect(() => {
    resize();
    const container = containerRef.current;
    let observer;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(resize);
      observer.observe(container);
    }
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      observer?.disconnect();
    };
  }, [resize]);

  const pointFrom = (event) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top, p: pressureScale(event) };
  };

  const onPointerDown = (event) => {
    const s = state.current;
    if (event.button !== 0 && event.pointerType === "mouse") return;
    if (event.pointerType === "touch" && s.penActive) return; // palm rejection
    if (s.current) return; // one stroke at a time
    if (event.pointerType === "pen") s.penActive = true;
    try {
      // keep receiving moves when the pen slips past the edge mid-stroke
      event.currentTarget.setPointerCapture?.(event.pointerId);
    } catch {
      // the pointer is already gone (or synthetic); drawing still works
    }
    s.pointerId = event.pointerId;
    s.current = { weight: s.weight, points: [pointFrom(event)] };
    s.strokes.push(s.current);
    s.undone = [];
    s.cleared = null;
    drawStroke(context(), s.current);
  };

  const onPointerMove = (event) => {
    const s = state.current;
    if (!s.current || event.pointerId !== s.pointerId) return;
    const samples = event.getCoalescedEvents?.() || [];
    const events = samples.length ? samples : [event];
    const from = s.current.points.length;
    for (const e of events) s.current.points.push(pointFrom(e));
    // the first dot was drawn as a circle; redraw from the start once it
    // becomes a line so the cap matches
    drawStroke(context(), s.current, from === 1 ? 1 : from);
  };

  const endStroke = (event) => {
    const s = state.current;
    if (!s.current || event.pointerId !== s.pointerId) return;
    if (event.pointerType === "pen") s.penActive = false;
    s.current = null;
    s.pointerId = null;
    onStrokeEnd?.();
  };

  useImperativeHandle(ref, () => ({
    setStrokeWeight: (w) => {
      state.current.weight = w;
    },
    undo: () => {
      const s = state.current;
      if (s.strokes.length === 0 && s.cleared) {
        s.strokes = s.cleared;
        s.cleared = null;
      } else if (s.strokes.length) {
        s.undone.push(s.strokes.pop());
      }
      repaint();
    },
    redo: () => {
      const s = state.current;
      if (s.undone.length) {
        s.strokes.push(s.undone.pop());
        repaint();
      }
    },
    clearCanvas: () => {
      const s = state.current;
      if (s.strokes.length) s.cleared = s.strokes;
      s.strokes = [];
      s.undone = [];
      s.current = null;
      repaint();
    },
    isEmpty: () => state.current.strokes.length === 0,
    // strokes in CSS pixels: [{weight, points: [{x, y, p}]}]
    getStrokes: () => state.current.strokes.map((st) => ({
      weight: st.weight,
      points: st.points.map((pt) => ({ ...pt })),
    })),
    // a 1x PNG with black ink on white and no guide line (a high-density
    // backing store would only make the upload bigger and slower)
    exportImage: () => {
      const s = state.current;
      const out = document.createElement("canvas");
      out.width = s.width;
      out.height = s.height;
      const ctx = out.getContext("2d");
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, s.width, s.height);
      for (const stroke of s.strokes) drawStroke(ctx, stroke);
      return out.toDataURL("image/png");
    },
  }), [repaint]);

  return (
    <div ref={containerRef} className="drawing" style={{ "--baseline": `${BASELINE_Y * 100}%` }}>
      <canvas
        ref={canvasRef}
        className="drawing__canvas"
        role="img"
        aria-label="Drawing area. Write an equation here with a mouse, finger or pen."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endStroke}
        onPointerCancel={endStroke}
      />
    </div>
  );
});

export default DrawingCanvas;
