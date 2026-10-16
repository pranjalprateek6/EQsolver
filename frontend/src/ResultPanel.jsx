import { Spinner } from "react-bootstrap";
import MathView from "./MathView";

// Plain-text fallback for when the server sends no LaTeX for the solution.
export function formatSolution(solution) {
  if (solution === "" || solution === null || solution === undefined) return "No solution";
  const trimmed = String(solution).trim();
  if (trimmed === "all values") return "True for every value";
  // sympy returns list-like strings such as "[-2, 2]"; show them plainly
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    const inner = trimmed.slice(1, -1).trim();
    return inner === "" ? "No solution" : inner;
  }
  return trimmed;
}

// Editable recognized equation plus the solution. The user can correct a
// misread before (or after) solving, which bridges the model's accuracy gap.
function ResultPanel({
  recognized,
  onRecognizedChange,
  onSolve,
  solving,
  latex,
  solution,
  solutionLatex,
  steps = [],
  solved,
  onShare,
  copied,
}) {
  const onKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSolve();
    }
  };

  return (
    <div className="result">
      {latex && <MathView latex={latex} className="result__math" />}
      <div className="result__field">
        <label className="result__label" htmlFor="recognized-input">
          Recognized equation
        </label>
        <span className="result__editrow">
          <input
            id="recognized-input"
            className="form-control result__input"
            value={recognized}
            onChange={(e) => onRecognizedChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Edit if the model misread"
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={onSolve}
            disabled={solving}
          >
            {solving ? (
              <>
                <Spinner as="span" animation="border" size="sm" aria-hidden="true" />
                <span className="visually-hidden">Solving</span>
              </>
            ) : (
              "Solve"
            )}
          </button>
        </span>
        <span className="result__hint">
          Fix any wrong characters, then press Solve or Enter. Use <code>^</code> for
          powers; <code>2x</code> means 2 times x.
        </span>
      </div>

      <div className="result__solution" aria-live="polite">
        <span className="result__solution-head">
          <span className="result__label">Solution</span>
          {solved && onShare && (
            <button type="button" className="result__share" onClick={onShare}>
              {copied ? "Link copied" : "Copy link"}
            </button>
          )}
        </span>
        {solved && solutionLatex ? (
          <MathView
            latex={solutionLatex}
            className="result__value result__value--math"
            label={formatSolution(solution)}
          />
        ) : (
          <span className={`result__value ${solved ? "" : "result__value--muted"}`}>
            {solved ? formatSolution(solution) : "Could not solve this. Check the equation above."}
          </span>
        )}
      </div>

      {solved && steps.length > 1 && (
        <details className="steps">
          <summary className="steps__toggle">Show steps ({steps.length - 1})</summary>
          <ol className="steps__list">
            {steps.map((step, index) => (
              <li key={index} className="steps__item">
                <span className="steps__title">{step.title}</span>
                <MathView latex={step.latex} className="steps__math" />
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

export default ResultPanel;
