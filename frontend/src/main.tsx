import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { Admin } from "./Admin";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {window.location.pathname.startsWith("/admin") ? <Admin /> : <App />}
  </React.StrictMode>,
);
