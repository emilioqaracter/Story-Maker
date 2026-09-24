import { useParams, type RouteObject } from "react-router";

import { Home } from "./commons/shell/Home";
import { Layout } from "./commons/shell/Layout";
import { NotFound } from "./commons/shell/NotFound";
import { Band } from "./commons/ui/Band";
import { Graph } from "./entity-graph/Graph";
import { interviewRoutes } from "./interview/routes";
import { manuscriptRoutes } from "./manuscript/routes";
import { Debt } from "./narrative-debt/Debt";
import { Status } from "./run-health/Status";
import { storyBibleRoutes } from "./story-bible/routes";

/**
 * Raiz de composicion (spec D-68, `architecture.md` §2.3): conoce a todas las
 * funcionalidades y ninguna la conoce a ella. Monta las diez direcciones de
 * RF-165, relativas a la base `/app/` (D-67), y ninguna mas.
 *
 * La deuda y el grafo no tienen direccion propia en RF-165: se muestran dentro
 * de `/novels/{id}/status`, junto al estado de la tirada.
 */
function StatusPage() {
  const { id = "" } = useParams();
  return (
    <>
      <Band art="estado-pista" eyebrow="Estado" title="Cómo va la novela" />
      <Status novel={id} />
      <Debt novel={id} />
      <Graph novel={id} />
    </>
  );
}

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      ...interviewRoutes,
      ...manuscriptRoutes,
      ...storyBibleRoutes,
      { path: "novels/:id/status", element: <StatusPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

/** Las direcciones de RF-165, tal como se montan. Las comprueba `routes.test.tsx`. */
export function addresses(): string[] {
  const children = routes[0]?.children ?? [];
  return children.filter((r) => r.path !== "*").map((r) => (r.index ? "/" : `/${r.path ?? ""}`));
}
