import React from "react";
import { createRoot } from "react-dom/client";
// import Bootstrap first so our own styles (index.css, App.css) override it
import "bootstrap/dist/css/bootstrap.min.css";
import "@fontsource/source-code-pro/400.css";
import "@fontsource/source-code-pro/600.css";
import "@fontsource/source-code-pro/700.css";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
