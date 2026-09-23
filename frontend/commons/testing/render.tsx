import { render } from "@testing-library/react";
import { MemoryRouter, useLocation, useRoutes, type RouteObject } from "react-router";

/**
 * Monta unas rutas en una direccion, como lo haria el navegador bajo `/app/`.
 *
 * Con `MemoryRouter` y no con el router de datos: el de datos crea un `Request`
 * por navegacion, y en jsdom su `AbortSignal` no es el de `fetch`, asi que
 * cualquier `navigate()` falla en la prueba y no en la aplicacion.
 */
export function renderAt(routes: RouteObject[], path: string) {
  const where = { pathname: path };

  function Capture() {
    where.pathname = useLocation().pathname;
    return null;
  }

  function App() {
    return useRoutes(routes);
  }

  const result = render(
    <MemoryRouter initialEntries={[path]}>
      <Capture />
      <App />
    </MemoryRouter>,
  );
  return { ...result, router: { state: { location: where } } };
}
