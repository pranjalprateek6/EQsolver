import { Spinner } from "react-bootstrap";
import MathView from "./MathView";

// Editable recognized equation plus the solution. The user can correct a
// misread before (or after) solving, which bridges the model's accuracy gap.
function formatSolution(solution) {
  if (solution === "" || solution === null || solution === undefined) return "no solution";
  // sympy returns list-like strings such as "[-2, 2]"; show them plainly
  const trimmed = String(solution).trim();
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    const inner = trimmed.slice(1, -1).trim();
    if (inner === "") return "no solution";
    return `x = ${inner}`;
  }
  return trimmed;
}

function ResultPanel({
  recognized,
  onRecognizedChange,
  onSolve,
  solving,
  latex,
  solution,
  solved,
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
      <label className="result__field">
        <span className="result__label">Recognized equation</span>
        <span className="result__editrow">
          <input
            className="form-control result__input"
            value={recognized}
            onChange={(e) => onRecognizedChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="edit if the model misread"
            spellCheck={false}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={onSolve}
            disabled={solving}
          >
            {solving ? <Spinner as="span" animation="border" size="sm" /> : "Solve"}
          </button>
        </span>
        <span className="result__hint">
          Fix any wrong characters above, then press Solve or Enter.
        </span>
      </label>

      <div className="result__solution">
        <span className="result__label">Solution</span>
        <span className={`result__value ${solved ? "" : "result__value--muted"}`}>
          {solved ? formatSolution(solution) : "could not solve, check the equation"}
        </span>
      </div>
    </div>
  );
}

export default ResultPanel;
