import React, { Component } from "react";
import P5Wrapper from "react-p5-wrapper";
import { Alert, Spinner } from "react-bootstrap";
import sketch from "./sketches/sketch";
import UploadButton from "./UploadButton";
import Output from "./Output";
import "bootstrap/dist/css/bootstrap.min.css";

const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:5000";

class Canvas extends Component {
  constructor() {
    super();
    this.state = {
      clearCount: 0,
      loading: false,
      error: "",
      equation: "",
      formatted_equation: "",
      result: "",
    };
  }

  sendImgToServer = (image) => {
    // strip any data-URL prefix (canvas gives png, uploads may be jpeg)
    const img = image.replace(/^data:image\/\w+;base64,/, "");

    this.setState({
      loading: true,
      error: "",
      equation: "",
      formatted_equation: "",
      result: "",
    });

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
        this.setState({
          loading: false,
          equation: data.entered_equation,
          formatted_equation: data.formatted_equation,
          result: data.solution,
        });
      })
      .catch((error) => {
        this.setState({
          loading: false,
          error: error.message || "could not reach the server",
        });
      });
  };

  onEvaluate = () => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return;
    this.sendImgToServer(canvas.toDataURL());
  };

  onClear = () => {
    this.setState((prev) => ({
      clearCount: prev.clearCount + 1,
      error: "",
      equation: "",
      formatted_equation: "",
      result: "",
    }));
  };

  render() {
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
            <P5Wrapper sketch={sketch} clearCount={this.state.clearCount}></P5Wrapper>
          </div>
          <div className="col-6 col-md-2">
            <div className="row">
              <div className="col">
                <button
                  type="button"
                  onClick={this.onEvaluate}
                  disabled={this.state.loading}
                  className="btn btn-primary btn-block "
                >
                  {this.state.loading ? (
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
                  onClick={this.onClear}
                  disabled={this.state.loading}
                  className="btn btn-danger btn-block "
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
            {this.state.error && (
              <Alert variant="danger">{this.state.error}</Alert>
            )}
          </div>
        </div>
        <br />
        <div className="row">
          <div className="offset-md-3">
            <UploadButton
              sendImgToServer={this.sendImgToServer}
              disabled={this.state.loading}
            />
          </div>
        </div>
        <br />
        <br />
        <Output
          equation={this.state.equation}
          formatted_equation={this.state.formatted_equation}
          result={this.state.result}
        />
      </div>
    );
  }
}

export default Canvas;
