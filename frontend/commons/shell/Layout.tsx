import { Link, NavLink, Outlet, useParams } from "react-router";

import { Marca } from "../brand/Marca";

/**
 * Armazon: cabecera y, dentro de una novela, su navegacion. Sin ningun control del ciclo.
 *
 * La cabecera va siempre en el azul de titulares, tambien en tema claro: el logo
 * solo existe en negativo y sobre fondo claro desaparece (BRAND.md §2 y §5). Es
 * el unico sitio donde aparece, arriba a la izquierda y en el mismo punto en
 * todas las vistas.
 */
export function Layout() {
  const { id } = useParams();
  return (
    <div className="shell">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <header className="shell-header">
        <div className="shell-brand">
          <Marca alto={24} />
          <Link to="/" className="brand">
            Story Maker
          </Link>
        </div>
        {id !== undefined && (
          <nav aria-label="Novela" className="shell-nav">
            <NavLink to={`/novels/${id}`} end>
              Lectura
            </NavLink>
            <NavLink to={`/novels/${id}/bible`}>Personajes y lugares</NavLink>
            <NavLink to={`/novels/${id}/changes`}>Cambios</NavLink>
            <NavLink to={`/novels/${id}/status`}>Estado</NavLink>
          </nav>
        )}
      </header>
      <main className="shell-main" id="contenido" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
