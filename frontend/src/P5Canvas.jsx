import { useEffect, useRef } from "react";
import p5 from "p5";
import sketch from "./sketches/sketch";

// Thin wrapper that mounts a p5 instance and exposes it through instanceRef.
function P5Canvas({ instanceRef }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const instance = new p5(sketch, containerRef.current);
    if (instanceRef) instanceRef.current = instance;
    return () => {
      if (instanceRef) instanceRef.current = null;
      instance.remove();
    };
  }, [instanceRef]);

  return <div ref={containerRef} />;
}

export default P5Canvas;
