import type { RouteObject } from "react-router";

import { Interview } from "./Interview";
import { NewInterview } from "./NewInterview";

/** RF-165, RF-167. Las monta la raiz de composicion. */
export const interviewRoutes: RouteObject[] = [
  { path: "new", element: <NewInterview /> },
  { path: "interviews/:iid", element: <Interview /> },
];
