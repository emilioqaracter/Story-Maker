import type { ReactNode } from "react";

import { illustration, type ArtId } from "../brand/art";

/**
 * La banda que abre una vista (`specs/srs-frontend-v2.md` RF-280): una
 * ilustracion del catalogo bajo un velo en el azul de titulares, y encima el
 * titulo de la vista. La ilustracion es decorativa, con texto alternativo vacio;
 * si todavia no se ha generado, queda el degradado de la marca (RF-277).
 * Nunca se usa dentro de la lectura de un capitulo.
 */
export function Band({ art, eyebrow, title, children }: { art: ArtId; eyebrow?: string; title: string; children?: ReactNode }) {
  const src = illustration(art);
  return (
    <header className={src ? "band" : "band band-plain"}>
      {src && <img className="band-art" src={src} alt="" decoding="async" />}
      <div className="band-body">
        {eyebrow && <p className="band-eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {children}
      </div>
    </header>
  );
}
