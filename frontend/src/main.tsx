import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles.css";

/*
  Punto de entrada principal de React.

  React busca el elemento con id="root"
  definido en index.html y renderiza ahí
  toda la aplicación.
*/
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);