import { useState } from "react";

// Every symbol the model can read, for picking one it did not suggest.
export const ALL_SYMBOLS = [
  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
  "+", "-", "×", "÷", "=", "(", ")", "√", "x", "y", "z",
];

function confidenceLevel(confidence) {
  if (confidence >= 0.6) return "high";
  if (confidence >= 0.3) return "medium";
  return "low";
}

const percent = (value) => `${Math.round(value * 100)}%`;

// Shows what the model actually saw: one tile per segmented character with
// its symbol and confidence. Low-confidence tiles are tinted so the user knows
// which reads to double-check, and tapping a tile offers the model's other
// guesses (and every symbol) as a one-tap correction.
function SegmentationStrip({ characters, onCorrect, disabled }) {
  const [open, setOpen] = useState(null);
  if (!characters || characters.length === 0) return null;

  const selected = open !== null ? characters[open] : null;
  const suggestions = (selected?.alternatives || []).filter((a) => a.char !== selected?.char);

  const pick = (char) => {
    const index = open;
    setOpen(null);
    if (char !== characters[index].char) onCorrect?.(index, char);
  };

  return (
    <div className="segmentation">
      <div className="segmentation__label">
        What the model saw ({characters.length} character
        {characters.length === 1 ? "" : "s"}){onCorrect && " · tap one to fix it"}
      </div>
      <div className="segmentation__strip">
        {characters.map((char, index) => (
          <button
            type="button"
            key={index}
            className={`glyph glyph--${confidenceLevel(char.confidence)} ${
              open === index ? "glyph--open" : ""
            }`}
            onClick={() => setOpen(open === index ? null : index)}
            disabled={disabled || !onCorrect}
            aria-expanded={open === index}
            aria-label={`Character ${index + 1}: read as ${char.char}, ${percent(
              char.confidence
            )} sure. Tap to change.`}
          >
            <img className="glyph__img" src={char.image} alt="" />
            <span className="glyph__caption">
              <span className="glyph__char">{char.char}</span>
              <span className="glyph__conf">{percent(char.confidence)}</span>
            </span>
          </button>
        ))}
      </div>

      {selected && (
        <div className="glyph-picker" role="group" aria-label={`Change character ${open + 1}`}>
          {suggestions.length > 0 && (
            <div className="glyph-picker__row">
              <span className="glyph-picker__label">Did you mean</span>
              {suggestions.map((alt) => (
                <button
                  type="button"
                  key={alt.char}
                  className="glyph-picker__option glyph-picker__option--suggested"
                  onClick={() => pick(alt.char)}
                >
                  {alt.char}
                  <span className="glyph-picker__conf">{percent(alt.confidence)}</span>
                </button>
              ))}
            </div>
          )}
          <div className="glyph-picker__row">
            <span className="glyph-picker__label">Or pick</span>
            {ALL_SYMBOLS.map((symbol) => (
              <button
                type="button"
                key={symbol}
                className={`glyph-picker__option ${
                  symbol === selected.char ? "glyph-picker__option--current" : ""
                }`}
                onClick={() => pick(symbol)}
                aria-pressed={symbol === selected.char}
              >
                {symbol}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default SegmentationStrip;
