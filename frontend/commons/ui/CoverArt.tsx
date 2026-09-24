import { coverFor, illustration } from "../brand/art";

/**
 * La portada de una novela en plano: la ilustracion que le toca (RF-278), el
 * titulo y, si lo hay, el destinatario. La usan la miniatura de la lista y la
 * tapa del libro en 3D. Es decorativa: quien la monta da el nombre accesible.
 */
export function CoverArt({ novel, title, recipient }: { novel: string; title: string; recipient?: string }) {
  const src = illustration(coverFor(novel));
  return (
    <div className={src ? "cover-art" : "cover-art cover-art-plain"} aria-hidden="true">
      {src && <img src={src} alt="" decoding="async" />}
      <div className="cover-art-text">
        <p className="cover-art-title">{title}</p>
        {recipient && <p className="cover-art-for">Para {recipient}</p>}
      </div>
    </div>
  );
}
