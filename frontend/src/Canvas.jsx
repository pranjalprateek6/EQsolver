import { useRef, useState } from "react";
import { Alert, Spinner } from "react-bootstrap";
import P5Canvas from "./P5Canvas";
import UploadButton from "./UploadButton";
import Output from "./Output";
import "bootstrap/dist/css/bootstrap.min.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";

const EMPTY_RESULT = { equation: "", formatted_equation: "", result: "" };

function Canvas() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [output, setOutput] = useState(EMPTY_RESULT);
  const p5Ref = useRef(null);

  const sendImgToServer = (image) => {
    // strip any data-URL prefix (canvas gives png, uploads may be jpeg)
    const img = image.replace(/^data:image\/\w+;base64,/, "");

    setLoading(true);
    setError("");
    setOutput(EMPTY_RESULT);

    fetch(`${API_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ image: img }),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || `request failed (${response.status})`);
        }
        return data;
      })
      .then((data) => {
        setOutput({
          equation: data.entered_equation,
          formatted_equation: data.formatted_equation,
          result: data.solution,
        });
      })
      .catch((err) => {
        setError(err.message || "could not reach the server");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const onEvaluate = () => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return;
    sendImgToServer(canvas.toDataURL());
  };

  const onClear = () => {
    p5Ref.current?.clearCanvas();
    setError("");
    setOutput(EMPTY_RESULT);
  };

  return (
    <div className="container ">
      <br />
      <div className="row">
        <div className="col-sm-12 col-md-6 offset-md-2">
          Draw the equation below
        </div>
      </div>
      <br />
      <div className="row align-items-center">
        <div className="col-12 col-md-6 border border-dark offset-md-2">
          <P5Canvas instanceRef={p5Ref} />
        </div>
        <div className="col-6 col-md-2">
          <div className="row">
            <div className="col">
              <button
                type="button"
                onClick={onEvaluate}
                disabled={loading}
                className="btn btn-primary w-100"
              >
                {loading ? (
                  <>
                    <Spinner as="span" animation="border" size="sm" />{" "}
                    Evaluating...
                  </>
                ) : (
                  "Evaluate"
                )}
              </button>
            </div>
          </div>
          <br />
          <div className="row">
            <div className="col">
              <button
                type="button"
                onClick={onClear}
                disabled={loading}
                className="btn btn-danger w-100"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      </div>
      <br />
      <div className="row">
        <div className="col-12 col-md-6 offset-md-2">
          {error && <Alert variant="danger">{error}</Alert>}
        </div>
      </div>
      <br />
      <div className="row">
        <div className="offset-md-3">
          <UploadButton sendImgToServer={sendImgToServer} disabled={loading} />
        </div>
      </div>
      <br />
      <br />
      <Output
        equation={output.equation}
        formatted_equation={output.formatted_equation}
        result={output.result}
      />
    </div>
  );
}

export default Canvas;
