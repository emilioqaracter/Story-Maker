import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import "./commons/shell/style.css";
import { routes } from "./routes";

/** Punto de entrada. La aplicacion vive bajo `/app/` (spec D-67). */
const router = createBrowserRouter(routes, { basename: "/app" });

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
}
