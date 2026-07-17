import { useRef, useState } from "react";
import { Alert, Spinner } from "react-bootstrap";
import P5Canvas from "./P5Canvas";
import UploadButton from "./UploadButton";
import SegmentationStrip from "./SegmentationStrip";
import ResultPanel from "./ResultPanel";
import "bootstrap/dist/css/bootstrap.min.css";
import "./App.css";

// In dev the API is on a separate port; in a production build the frontend is
// served by Flask itself, so calls go to the same origin (relative URLs).
const API_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "http://127.0.0.1:5000" : "");

const EMPTY = {
  characters: [],
  recognized: "",
  formatted: "",
  latex: "",
  solution: "",
  solved: false,
};

// quick things to try without drawing (solved via the /solve endpoint)
const EXAMPLES = ["8+3", "x**2-5*x+6=0", "sqrt(144)", "(x+1)/2=4"];

function Canvas() {
  const [brush, setBrush] = useState(4);
  const [loading, setLoading] = useState(false);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(EMPTY);
  const [recognized, setRecognized] = useState("");
  const p5Ref = useRef(null);

  const post = (path, payload) =>
    fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(async (response) => {
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `request failed (${response.status})`);
      }
      return data;
    });

  const sendImgToServer = (image) => {
    const img = image.replace(/^data:image\/\w+;base64,/, "");
    setLoading(true);
    setError("");
    setResult(EMPTY);
    setRecognized("");

    post("/predict", { image: img })
      .then((data) => {
        setResult({
          characters: data.characters,
          recognized: data.recognized,
          formatted: data.formatted_equation,
          latex: data.latex,
          solution: data.solution,
          solved: data.solved,
        });
        setRecognized(data.recognized);
      })
      .catch((err) => setError(err.message || "could not reach the server"))
      .finally(() => setLoading(false));
  };

  const onEvaluate = () => {
    const p5 = p5Ref.current;
    if (!p5 || p5.isEmpty()) {
      setError("draw an equation first");
      return;
    }
    sendImgToServer(p5.exportImage());
  };

  const solveExpr = (expression) => {
    if (!expression) return;
    setSolving(true);
    setError("");

    post("/solve", { expression })
      .then((data) => {
        setResult((prev) => ({
          ...prev,
          recognized: expression,
          formatted: data.formatted_equation,
          latex: data.latex,
          solution: data.solution,
          solved: true,
        }));
      })
      .catch((err) => setError(err.message || "could not solve that expression"))
      .finally(() => setSolving(false));
  };

  const onSolveEdited = () => solveExpr(recognized.trim());

  const onExample = (expression) => {
    setError("");
    setResult({ ...EMPTY, recognized: expression });
    setRecognized(expression);
    solveExpr(expression);
  };

  const onBrushChange = (value) => {
    setBrush(value);
    p5Ref.current?.setStrokeWeight(value);
  };

  const onUndo = () => p5Ref.current?.undo();

  const onClear = () => {
    p5Ref.current?.clearCanvas();
    setError("");
    setResult(EMPTY);
    setRecognized("");
  };

  const hasResult = result.characters.length > 0 || result.recognized;

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">EQsolver</h1>
        <p className="app-subtitle">
          Draw an equation and let the model read and solve it.
        </p>
      </header>

      <section className="board">
        <div className="canvas-frame">
          <P5Canvas instanceRef={p5Ref} />
        </div>

        <div className="toolbar">
          <label className="brush">
            <span>Brush</span>
            <input
              type="range"
              min="2"
              max="10"
              value={brush}
              onChange={(e) => onBrushChange(Number(e.target.value))}
            />
          </label>
          <div className="toolbar__actions">
            <button type="button" className="btn btn-outline-secondary" onClick={onUndo}>
              Undo
            </button>
            <button type="button" className="btn btn-outline-danger" onClick={onClear}>
              Clear
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onEvaluate}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Spinner as="span" animation="border" size="sm" /> Reading...
                </>
              ) : (
                "Evaluate"
              )}
            </button>
          </div>
        </div>

        <p className="hint">
          Supported: digits <code>0-9</code>, variables <code>x y z</code>,{" "}
          <code>+ - × ÷ =</code>, parentheses, powers (write small and raised),
          and roots. Write on the guide line.
        </p>

        <div className="examples">
          <span className="examples__label">Or try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              className="examples__chip"
              onClick={() => onExample(ex)}
              disabled={solving}
            >
              {ex}
            </button>
          ))}
        </div>

        <div className="upload-row">
          <UploadButton sendImgToServer={sendImgToServer} disabled={loading} />
        </div>
      </section>

      {error && (
        <Alert variant="danger" className="board-alert">
          {error}
        </Alert>
      )}

      {hasResult && (
        <section className="results">
          <SegmentationStrip characters={result.characters} />
          <ResultPanel
            recognized={recognized}
            onRecognizedChange={setRecognized}
            onSolve={onSolveEdited}
            solving={solving}
            latex={result.latex}
            solution={result.solution}
            solved={result.solved}
          />
        </section>
      )}
    </div>
  );
}

export default Canvas;
