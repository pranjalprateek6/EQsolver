import { useEffect, useRef } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

// Renders a LaTeX string with KaTeX. Falls back to plain text on error.
function MathView({ latex, className }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    if (!latex) {
      ref.current.textContent = "";
      return;
    }
    try {
      katex.render(latex, ref.current, { throwOnError: false, displayMode: true });
    } catch {
      ref.current.textContent = latex;
    }
  }, [latex]);

  return <div ref={ref} className={className} />;
}

export default MathView;
