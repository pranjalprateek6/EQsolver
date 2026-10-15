import { useEffect, useRef } from "react";

// KaTeX and its stylesheet are loaded on first use, so they stay out of the
// initial bundle the page needs before anyone has solved anything.
let katexPromise;
function loadKatex() {
  katexPromise ??= Promise.all([
    import("katex"),
    import("katex/dist/katex.min.css"),
  ]).then(([module]) => module.default);
  return katexPromise;
}

// Renders a LaTeX string with KaTeX. Shows the raw text until KaTeX loads,
// and falls back to it on error.
function MathView({ latex, className, label }) {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    node.textContent = latex || "";
    if (!latex) return undefined;

    let cancelled = false;
    loadKatex()
      .then((katex) => {
        if (cancelled) return;
        katex.render(latex, node, { throwOnError: false, displayMode: true });
      })
      .catch(() => {
        if (!cancelled) node.textContent = latex;
      });
    return () => {
      cancelled = true;
    };
  }, [latex]);

  return <div ref={ref} className={className} role="math" aria-label={label || latex} />;
}

export default MathView;
