import { CoverArt } from "../../commons/ui/CoverArt";

/**
 * La obra cerrada, entregada como libro (`specs/srs-frontend-v2.md` RF-281, D-117).
 *
 * Un escenario blanco en los dos temas y el libro en CSS 3D: tapa, lomo con el
 * titulo, canto de paginas, contratapa y sombra en el suelo. El angulo es fijo y
 * no responde al puntero: el libro se mira, no se navega. Para quien no lo ve,
 * es una sola imagen con su nombre.
 */
export function Book({ novel, title, recipient }: { novel: string; title: string; recipient?: string }) {
  return (
    <figure className="book-stage" role="img" aria-label={`Portada de ${title}`}>
      <div className="book-scene" aria-hidden="true">
        <div className="book">
          <div className="book-face book-front">
            <CoverArt novel={novel} title={title} recipient={recipient} />
          </div>
          <div className="book-face book-back" />
          <div className="book-face book-spine">
            <span>{title}</span>
          </div>
          <div className="book-face book-pages" />
          <div className="book-face book-top" />
          <div className="book-face book-bottom" />
        </div>
        <div className="book-floor" />
      </div>
    </figure>
  );
}
