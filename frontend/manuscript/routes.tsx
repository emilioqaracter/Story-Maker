import type { RouteObject } from "react-router";

import { Cover } from "./cover/Cover";
import { Chapter } from "./reading/Chapter";
import { Changes } from "./requests/Changes";

/** Las direcciones de la lectura y de las solicitudes (RF-165). Las monta la raiz de composicion. */
export const manuscriptRoutes: RouteObject[] = [
  { path: "novels/:id", element: <Cover /> },
  { path: "novels/:id/v/:v", element: <Cover /> },
  { path: "novels/:id/v/:v/chapters/:n", element: <Chapter /> },
  { path: "novels/:id/changes", element: <Changes /> },
];
