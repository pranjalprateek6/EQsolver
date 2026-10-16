import { useEffect, useRef, useState } from "react";
import { Alert, Spinner } from "react-bootstrap";
import DrawingCanvas from "./DrawingCanvas";
import SegmentationStrip from "./SegmentationStrip";
import MathView from "./MathView";
import { postJson } from "./api";

// ruled lines on the drawing surface, one equation on each
const RULES = 6;
// the server checks at most this many lines (checker.MAX_LINES)
const MAX_LINES = 12;

const SAMPLE = "2x+3=11\n2x=8\nx=4";

const STATUS = {
  true: { icon: "✓", label: "correct step", className: "ok" },
  false: { icon: "✗", label: "this step changes the solutions", className: "bad" },
  null: { icon: "?", label: "could not check this step", className: "unknown" },
};

function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function linesFrom(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function summary(result) {
  if (result.first_error !== null && result.first_error !== undefined) {
    const n = result.first_error + 1;
    return n === 1
      ? { tone: "bad", text: "There is a problem with line 1. Fix it, then check again." }
      : { tone: "bad", text: `Line ${n} does not follow from line ${n - 1}.` };
  }
  if (result.lines.some((line) => line.ok === null)) {
    return { tone: "unknown", text: "No mistakes found, but some steps could not be checked." };
  }
  if (result.finished) return { tone: "ok", text: "Every step checks out, and you reached the answer." };
  if (result.lines.length < 2) {
    return { tone: "unknown", text: "Write your next step under the problem, then check again." };
  }
  return { tone: "ok", text: "Every step so far checks out. Keep going." };
}

// "Check my work": the student writes their working one equation per line
// (drawn on a ruled surface, or typed) and each line is checked against the
// one before it. The first line that changes the solutions is flagged with a
// hint; the answer itself stays hidden unless the student asks for it.
function CheckWork() {
  const [input, setInput] = useState("draw");
  const [typed, setTyped] = useState("");
  const [brush, setBrush] = useState(4);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [answer, setAnswer] = useState("");
  const [fixing, setFixing] = useState(null);
  const drawingRef = useRef(null);
  const requestRef = useRef(null);

  useEffect(() => () => requestRef.current?.abort(), []);

  const send = (payload, { characters } = {}) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setError("");
    return postJson("/check", payload, { signal: controller.signal })
      .then((data) => {
        // a typed re-check has no glyphs; keep the ones each line was read from
        const lines = data.lines.map((line, i) => ({
          ...line,
          characters: line.characters || characters?.[i] || null,
        }));
        setResult({ ...data, lines });
        if (data.answer_latex !== undefined) setAnswer(data.answer_latex);
        return data;
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      })
      .finally(() => {
        if (requestRef.current === controller) setBusy(false);
      });
  };

  // a fresh check of new working: never leave the last verdict on screen
  const startCheck = (payload, options) => {
    setResult(null);
    setAnswer("");
    setFixing(null);
    return send(payload, options);
  };

  const onCheck = () => {
    if (input === "draw") {
      const drawing = drawingRef.current;
      if (!drawing || drawing.isEmpty()) {
        setError("Write your working first, one equation on each ruled line.");
        return;
      }
      const image = drawing.exportImage().replace(/^data:image\/\w+;base64,/, "");
      startCheck({ image });
      return;
    }
    const lines = linesFrom(typed);
    if (lines.length === 0) {
      setError("Type your working first, one equation per line.");
      return;
    }
    if (lines.length > MAX_LINES) {
      setError(`That is more than ${MAX_LINES} lines. Check a shorter stretch of working.`);
      return;
    }
    startCheck({ lines });
  };

  const currentLines = () => result.lines.map((line) => line.text);

  const onReveal = () => {
    send(
      { lines: currentLines(), reveal: true },
      { characters: result.lines.map((line) => line.characters) }
    );
  };

  // a glyph in one handwritten line was corrected: re-read that line from
  // its glyphs (keeping their positions), then check the working again
  const onCorrect = (lineIndex) => (index, char) => {
    const characters = result.lines.map((line) => line.characters);
    const glyphs = characters[lineIndex].map((c, i) =>
      i === index ? { ...c, char, confidence: 1 } : c
    );
    characters[lineIndex] = glyphs;
    const controller = new AbortController();
    requestRef.current?.abort();
    requestRef.current = controller;
    setBusy(true);
    setError("");
    postJson(
      "/rebuild",
      { characters: glyphs.map(({ char: ch, x, y, w, h }) => ({ char: ch, x, y, w, h })) },
      { signal: controller.signal }
    )
      .then((data) => {
        const lines = currentLines();
        lines[lineIndex] = data.recognized;
        return send({ lines }, { characters });
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err.message);
          setBusy(false);
        }
      });
  };

  // carry the recognized lines into the text box for hand-editing
  const onEditAsText = () => {
    setTyped(currentLines().join("\n"));
    setInput("type");
  };

  const onClear = () => {
    requestRef.current?.abort();
    drawingRef.current?.clearCanvas();
    setBusy(false);
    setError("");
    setResult(null);
    setAnswer("");
    setFixing(null);
  };

  const onBrushChange = (value) => {
    setBrush(value);
    drawingRef.current?.setStrokeWeight(value);
  };

  const status = result && summary(result);

  return (
    <div className="workspace">
      <section className="panel board" aria-label="Your working">
        <div className="input-switch" role="group" aria-label="How to enter your working">
          <button
            type="button"
            className={`input-switch__option ${input === "draw" ? "is-active" : ""}`}
            aria-pressed={input === "draw"}
            onClick={() => setInput("draw")}
          >
            Write
          </button>
          <button
            type="button"
            className={`input-switch__option ${input === "type" ? "is-active" : ""}`}
            aria-pressed={input === "type"}
            onClick={() => setInput("type")}
          >
            Type
          </button>
        </div>

        {/* kept mounted while typing so the drawing survives a switch */}
        <div className="canvas-frame" hidden={input !== "draw"}>
          <DrawingCanvas
            ref={drawingRef}
            aspect={1}
            narrowAspect={1.35}
            rules={RULES}
            label="Ruled drawing area. Write one equation of your working on each line."
          />
        </div>

        {input === "type" && (
          <div className="typed-work">
            <label className="result__label" htmlFor="typed-work">
              Your working, one equation per line
            </label>
            <textarea
              id="typed-work"
              className="form-control typed-work__input"
              rows={7}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={SAMPLE}
              spellCheck={false}
              autoCapitalize="off"
              autoComplete="off"
            />
          </div>
        )}

        <div className="toolbar">
          {input === "draw" ? (
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
          ) : (
            <span />
          )}
          <div className="toolbar__actions">
            {input === "draw" && (
              <>
                <button type="button" className="btn btn-outline-secondary"
                  onClick={() => drawingRef.current?.undo()}>
                  Undo
                </button>
                <button type="button" className="btn btn-outline-danger" onClick={onClear}>
                  Clear
                </button>
              </>
            )}
            <button type="button" className="btn btn-primary" onClick={onCheck} disabled={busy}>
              {busy ? (
                <>
                  <Spinner as="span" animation="border" size="sm" aria-hidden="true" /> Checking...
                </>
              ) : (
                "Check"
              )}
            </button>
          </div>
        </div>

        <p className="hint">
          Write the problem on the first line and each step of your working on
          the next, one equation per line. Each line is checked against the one
          above it; the answer stays hidden unless you ask for it.
        </p>
      </section>

      <section className="panel results" aria-label="Check results" aria-busy={busy}>
        {error && (
          <Alert variant="danger" className="board-alert" role="alert">
            {error}
          </Alert>
        )}
        {result ? (
          <div className="check">
            <p className={`check__summary check__summary--${status.tone}`} role="status">
              {status.text}
            </p>
            <ol className="check__lines">
              {result.lines.map((line, index) => {
                const state = STATUS[String(line.ok)];
                const first = index === result.first_error;
                return (
                  <li
                    key={index}
                    className={`check__line check__line--${state.className} ${
                      first ? "check__line--first" : ""
                    }`}
                  >
                    <div className="check__row">
                      <span className="check__num">{index + 1}</span>
                      <span
                        className={`check__mark check__mark--${state.className}`}
                        role="img"
                        aria-label={index === 0 && line.ok ? "the problem" : state.label}
                      >
                        {index === 0 && line.ok ? "•" : state.icon}
                      </span>
                      {line.latex ? (
                        <MathView latex={line.latex} className="check__math" label={line.text} />
                      ) : (
                        <code className="check__text">{line.text || "(blank)"}</code>
                      )}
                      {line.characters && (
                        <button
                          type="button"
                          className="check__fix"
                          aria-expanded={fixing === index}
                          onClick={() => setFixing(fixing === index ? null : index)}
                        >
                          {fixing === index ? "Done" : "Fix reading"}
                        </button>
                      )}
                    </div>
                    {line.reason && (first || line.ok === null) && (
                      <p className="check__hint">
                        {first && <strong>Hint: </strong>}
                        {capitalize(line.reason)}.
                      </p>
                    )}
                    {fixing === index && line.characters && (
                      <SegmentationStrip
                        characters={line.characters}
                        onCorrect={onCorrect(index)}
                        disabled={busy}
                      />
                    )}
                  </li>
                );
              })}
            </ol>
            <div className="check__actions">
              <button type="button" className="result__share" onClick={onEditAsText}>
                Edit as text
              </button>
              {answer ? null : (
                <button type="button" className="result__share" onClick={onReveal}
                  disabled={busy}>
                  Show the answer
                </button>
              )}
            </div>
            {answer && (
              <div className="check__answer">
                <span className="result__label">Answer to line 1</span>
                <MathView latex={answer} className="result__value result__value--math" />
              </div>
            )}
          </div>
        ) : busy ? (
          <div className="results__empty" role="status">
            <Spinner animation="border" aria-hidden="true" />
            <span className="results__empty-title">Checking your working...</span>
          </div>
        ) : (
          !error && (
            <div className="results__empty">
              <span className="results__empty-title">Check each step of your working</span>
              <span className="results__empty-sub">
                Write a problem and your steps, one per line, then press Check.
                The first step that goes wrong is flagged with a hint.
              </span>
            </div>
          )
        )}
      </section>
    </div>
  );
}

export default CheckWork;
