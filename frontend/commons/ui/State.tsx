import type { ReactNode } from "react";

/**
 * Los dos estados que pinta cada vista mientras no hay datos que mostrar. Son
 * presentacion: el texto lo decide quien los usa y nada de aqui toca el ciclo.
 *
 * `Loading` es una region viva educada: un lector de pantalla anuncia la espera
 * sin interrumpir, y el indicador no parpadea (BRAND.md §4, «nada parpadea»).
 */
export function Loading({ children }: { children: ReactNode }) {
  return (
    <p className="loading" role="status" aria-live="polite">
      {children}
    </p>
  );
}

/** Un vacio explicado, nunca una pantalla en blanco. `action` es un enlace de navegacion, si lo hay. */
export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <p>{children}</p>
      {action}
    </div>
  );
}
