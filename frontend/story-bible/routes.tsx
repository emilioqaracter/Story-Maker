import type { RouteObject } from "react-router";

import { EntityCard } from "./EntityCard";
import { EntityList } from "./EntityList";

/** RF-165. Las monta la raiz de composicion. */
export const storyBibleRoutes: RouteObject[] = [
  { path: "novels/:id/bible", element: <EntityList /> },
  { path: "novels/:id/bible/:eid", element: <EntityCard /> },
];
