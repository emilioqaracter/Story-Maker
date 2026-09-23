import { Link, NavLink, Outlet, useParams } from "react-router";

/** Armazon: cabecera y, dentro de una novela, su navegacion. Sin ningun control del ciclo. */
export function Layout() {
  const { id } = useParams();
  return (
    <div className="shell">
      <header className="shell-header">
        <Link to="/" className="brand">
          Story Maker
        </Link>
        {id !== undefined && (
          <nav aria-label="Novela">
            <NavLink to={`/novels/${id}`} end>
              Lectura
            </NavLink>
            <NavLink to={`/novels/${id}/bible`}>Personajes y lugares</NavLink>
            <NavLink to={`/novels/${id}/changes`}>Cambios</NavLink>
            <NavLink to={`/novels/${id}/status`}>Estado</NavLink>
          </nav>
        )}
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
    </div>
  );
}
