import { Link } from "react-router";

/**
 * «No existe», explicito (RF-164). Nunca una novela vacia: un identificador que
 * el backend no conoce no es una novela sin capitulos (RI-10).
 */
export function NotFound({ detail }: { detail?: string }) {
  return (
    <section className="notice" role="alert">
      <h2>No existe</h2>
      <p>{detail ? detail : "Esta dirección no corresponde a nada que el sistema conozca."}</p>
      <p>
        <Link to="/">Volver al inicio</Link>
      </p>
    </section>
  );
}
