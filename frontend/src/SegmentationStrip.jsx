// Shows what the model actually saw: one tile per segmented character with
// its predicted symbol and confidence. Low-confidence tiles are tinted so
// the user knows which reads to double-check.
function confidenceLevel(confidence) {
  if (confidence >= 0.6) return "high";
  if (confidence >= 0.3) return "medium";
  return "low";
}

function SegmentationStrip({ characters }) {
  if (!characters || characters.length === 0) return null;

  return (
    <div className="segmentation">
      <div className="segmentation__label">
        What the model saw ({characters.length} character
        {characters.length === 1 ? "" : "s"})
      </div>
      <div className="segmentation__strip">
        {characters.map((char, index) => (
          <figure
            key={index}
            className={`glyph glyph--${confidenceLevel(char.confidence)}`}
            title={`raw label: ${char.raw} · confidence ${(char.confidence * 100).toFixed(0)}%`}
          >
            <img className="glyph__img" src={char.image} alt={`character ${char.char}`} />
            <figcaption className="glyph__caption">
              <span className="glyph__char">{char.char}</span>
              <span className="glyph__conf">{(char.confidence * 100).toFixed(0)}%</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

export default SegmentationStrip;
