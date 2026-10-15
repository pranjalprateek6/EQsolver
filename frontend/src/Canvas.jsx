import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Spinner } from "react-bootstrap";
import P5Canvas from "./P5Canvas";
import UploadButton, { readImageFile } from "./UploadButton";
import SegmentationStrip from "./SegmentationStrip";
import ResultPanel from "./ResultPanel";
import { postJson } from "./api";
import "./App.css";

const EMPTY = {
  characters: [],
  recognized: "",
  formatted: "",
  latex: "",
  solution: "",
  solutionLatex: "",
  solved: false,
};

// quick things to try without drawing (solved via the /solve endpoint)
const EXAMPLES = ["8+3", "x^2-5x+6=0", "sqrt(144)", "(x+1)/2=4"];

// after this long, explain that a sleeping server is waking up
const SLOW_NOTICE_MS = 3000;

function isTyping(target) {
  return target?.closest?.("input, textarea, [contenteditable='true']");
}

function Canvas() {
  const [brush, setBrush] = useState(4);
  const [loading, setLoading] = useState(false);
  const [solving, setSolving] = useState(false);
  const [slow, setSlow] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(EMPTY);
  const [recognized, setRecognized] = useState("");
  const p5Ref = useRef(null);
  const requestRef = useRef(null);

  const busy = loading || solving;

  useEffect(() => {
    if (!busy) {
      setSlow(false);
      return undefined;
    }
    const timer = setTimeout(() => setSlow(true), SLOW_NOTICE_MS);
    return () => clearTimeout(timer);
  }, [busy]);

  // only the latest request may update the screen; starting a new one
  // cancels whatever was still in flight
  const startRequest = () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    return controller;
  };

  const sendImgToServer = useCallback((image) => {
    const img = image.replace(/^data:image\/\w+;base64,/, "");
    const controller = startRequest();
    setLoading(true);
    setSolving(false);
    setError("");
    setResult(EMPTY);
    setRecognized("");

    postJson("/predict", { image: img }, { signal: controller.signal })
      .then((data) => {
        setResult({
          characters: data.characters,
          recognized: data.recognized,
          formatted: data.formatted_equation,
          latex: data.latex,
          solution: data.solution,
          solutionLatex: data.solution_latex || "",
          solved: data.solved,
        });
        setRecognized(data.recognized);
        if (data.message) setError(data.message);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      })
      .finally(() => {
        if (requestRef.current === controller) setLoading(false);
      });
  }, []);

  const onEvaluate = () => {
    const p5 = p5Ref.current;
    if (!p5 || p5.isEmpty()) {
      setError("Draw an equation first.");
      return;
    }
    sendImgToServer(p5.exportImage());
  };

  const solveExpr = (expression) => {
    if (!expression) return;
    const controller = startRequest();
    setSolving(true);
    setLoading(false);
    setError("");

    postJson("/solve", { expression }, { signal: controller.signal })
      .then((data) => {
        setResult((prev) => ({
          ...prev,
          recognized: expression,
          formatted: data.formatted_equation,
          latex: data.latex,
          solution: data.solution,
          solutionLatex: data.solution_latex || "",
          solved: true,
        }));
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err.message);
        // never leave the previous answer showing under a new equation
        setResult((prev) => ({
          ...prev,
          recognized: expression,
          latex: "",
          solution: "",
          solutionLatex: "",
          solved: false,
        }));
      })
      .finally(() => {
        if (requestRef.current === controller) setSolving(false);
      });
  };

  const onSolveEdited = () => solveExpr(recognized.trim());

  // the user tapped a glyph and picked another symbol: re-read the layout
  // with that glyph changed (positions are kept, so powers and fractions
  // still read correctly) and solve again
  const onCorrectGlyph = (index, char) => {
    const characters = result.characters.map((c, i) =>
      i === index ? { ...c, char, confidence: 1 } : c
    );
    const controller = startRequest();
    setResult((prev) => ({ ...prev, characters }));
    setSolving(true);
    setError("");

    const glyphs = characters.map(({ char: ch, x, y, w, h }) => ({ char: ch, x, y, w, h }));
    postJson("/rebuild", { characters: glyphs }, { signal: controller.signal })
      .then((data) => {
        setResult((prev) => ({
          ...prev,
          recognized: data.recognized,
          formatted: data.formatted_equation,
          latex: data.latex,
          solution: data.solution,
          solutionLatex: data.solution_latex || "",
          solved: data.solved,
        }));
        setRecognized(data.recognized);
        if (data.message) setError(data.message);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      })
      .finally(() => {
        if (requestRef.current === controller) setSolving(false);
      });
  };

  const onExample = (expression) => {
    setResult({ ...EMPTY, recognized: expression });
    setRecognized(expression);
    solveExpr(expression);
  };

  const onBrushChange = (value) => {
    setBrush(value);
    p5Ref.current?.setStrokeWeight(value);
  };

  const onUndo = () => p5Ref.current?.undo();
  const onRedo = () => p5Ref.current?.redo();

  const onClear = () => {
    requestRef.current?.abort();
    p5Ref.current?.clearCanvas();
    setLoading(false);
    setSolving(false);
    setError("");
    setResult(EMPTY);
    setRecognized("");
  };

  const readFile = useCallback(
    (file) => {
      readImageFile(file).then(sendImgToServer, (err) => setError(err.message));
    },
    [sendImgToServer]
  );

  // paste an image from the clipboard anywhere on the page
  useEffect(() => {
    const onPaste = (event) => {
      if (isTyping(event.target)) return;
      const file = [...(event.clipboardData?.files || [])].find((f) =>
        f.type.startsWith("image/")
      );
      if (file) {
        event.preventDefault();
        readFile(file);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [readFile]);

  // Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z or Ctrl+Y redo, unless typing
  useEffect(() => {
    const onKey = (event) => {
      if (isTyping(event.target) || !(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        event.preventDefault();
        p5Ref.current?.undo();
      } else if ((key === "z" && event.shiftKey) || key === "y") {
        event.preventDefault();
        p5Ref.current?.redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const dropHandlers = {
    onDragOver: (e) => {
      if ([...e.dataTransfer.types].includes("Files")) {
        e.preventDefault();
        setDragging(true);
      }
    },
    onDragLeave: () => setDragging(false),
    onDrop: (e) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) readFile(file);
    },
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

      <div className="workspace">
      <section className="panel board" aria-label="Drawing board">
        <div
          className={`canvas-frame ${dragging ? "canvas-frame--drop" : ""}`}
          {...dropHandlers}
        >
          <P5Canvas instanceRef={p5Ref} />
          {dragging && <div className="canvas-frame__drop">Drop the image to read it</div>}
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
            <button type="button" className="btn btn-outline-secondary" onClick={onUndo}
              title="Undo (Ctrl+Z)">
              Undo
            </button>
            <button type="button" className="btn btn-outline-secondary" onClick={onRedo}
              title="Redo (Ctrl+Shift+Z)">
              Redo
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
                  <Spinner as="span" animation="border" size="sm" aria-hidden="true" /> Reading...
                </>
              ) : (
                "Evaluate"
              )}
            </button>
          </div>
        </div>

        <p className="hint">
          Draw with: digits <code>0-9</code>, variables <code>x y z</code>,{" "}
          <code>+ - × ÷ =</code>, parentheses, powers (small and raised), and
          roots. For division draw <code>÷</code> or a fraction bar, not a slash.
          Keep symbols on the guide line.
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

      <section className="panel results" aria-label="Results" aria-busy={busy}>
        {error && (
          <Alert variant="danger" className="board-alert" role="alert">
            {error}
          </Alert>
        )}
        {busy && slow && (
          <p className="results__notice" role="status">
            Waking up the server. The first request after a quiet spell can take
            up to a minute; after that it is quick.
          </p>
        )}
        {loading ? (
          <div className="results__empty" role="status">
            <Spinner animation="border" aria-hidden="true" />
            <span className="results__empty-title">Reading your handwriting...</span>
          </div>
        ) : hasResult ? (
          <>
            <SegmentationStrip
              characters={result.characters}
              onCorrect={onCorrectGlyph}
              disabled={solving}
            />
            <ResultPanel
              recognized={recognized}
              onRecognizedChange={setRecognized}
              onSolve={onSolveEdited}
              solving={solving}
              latex={result.latex}
              solution={result.solution}
              solutionLatex={result.solutionLatex}
              solved={result.solved}
            />
          </>
        ) : (
          !error && (
            <div className="results__empty">
              <span className="results__empty-title">Your solution appears here</span>
              <span className="results__empty-sub">
                Draw an equation, upload a photo, or pick an example to get started.
              </span>
            </div>
          )
        )}
      </section>
      </div>
    </div>
  );
}

export default Canvas;
