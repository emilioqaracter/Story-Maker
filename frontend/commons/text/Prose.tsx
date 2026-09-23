/**
 * El unico componente que pinta texto largo, venga del modelo o de una persona
 * (RF-163, RNF-40). Cada parrafo es un nodo de texto: un `<script>` en la prosa
 * se lee como `<script>`, no se ejecuta.
 */

export interface Paragraph {
  /** Desplazamiento del parrafo dentro del texto original. */
  offset: number;
  text: string;
}

/**
 * Parte un texto en parrafos por lineas en blanco, conservando donde empieza
 * cada uno en el original. Pura (RNF-47): con los desplazamientos, una seleccion
 * se puede devolver al texto de la escena sin reconstruirla desde el DOM.
 */
export function paragraphs(text: string): Paragraph[] {
  const out: Paragraph[] = [];
  const separator = /\n[ \t]*\n\s*/g;
  let start = 0;
  for (const match of text.matchAll(separator)) {
    const end = match.index;
    if (end > start) out.push({ offset: start, text: text.slice(start, end) });
    start = end + match[0].length;
  }
  if (start < text.length) out.push({ offset: start, text: text.slice(start) });
  return out;
}

export function Prose({ text }: { text: string }) {
  return (
    <div className="prose">
      {paragraphs(text).map((p) => (
        <p key={p.offset} data-offset={p.offset}>
          {p.text}
        </p>
      ))}
    </div>
  );
}
