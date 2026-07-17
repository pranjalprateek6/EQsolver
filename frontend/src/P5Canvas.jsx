import { useEffect, useRef } from "react";
import p5 from "p5";
import makeSketch from "./sketches/sketch";

// aspect ratio of the drawing surface (height / width)
const ASPECT = 0.46;

// Mounts a p5 instance sized to its container so the internal resolution
// matches the displayed size 1:1, and keeps them in sync on resize.
function P5Canvas({ instanceRef }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    const width = container.clientWidth || 550;
    const height = Math.round(width * ASPECT);
    const instance = new p5(makeSketch(width, height), container);
    if (instanceRef) instanceRef.current = instance;

    let observer;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver((entries) => {
        const w = Math.round(entries[0].contentRect.width);
        if (w > 0 && Math.abs(w - instance.width) > 1 && instance.resizeTo) {
          instance.resizeTo(w, Math.round(w * ASPECT));
        }
      });
      observer.observe(container);
    }

    return () => {
      if (observer) observer.disconnect();
      if (instanceRef) instanceRef.current = null;
      instance.remove();
    };
  }, [instanceRef]);

  return <div ref={containerRef} style={{ width: "100%", lineHeight: 0 }} />;
}

export default P5Canvas;
