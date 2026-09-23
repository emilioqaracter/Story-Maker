import { Link } from "react-router";

import type { RunState } from "../../commons/api/run-state";
import { describeRun, inProgress } from "../../commons/api/run-state";
import type { ChapterEntry } from "../data";

/**
 * Indice (RF-178, RF-184): solo capitulos congelados, cada uno con enlace a su
 * lectura en esa version y con su marca de cambiado. Lo que aun se esta
 * escribiendo no aparece como capitulo sino como una sola linea de estado de
 * RI-03. Un borrador no sale del backend y aqui no se pide.
 */
export function Toc({
  novel,
  version,
  chapters,
  run,
}: {
  novel: string;
  version: number;
  chapters: readonly ChapterEntry[];
  run: RunState | undefined;
}) {
  return (
    <section className="toc">
      <h2>Índice</h2>
      {chapters.length === 0 ? (
        <p>Todavía no hay ningún capítulo congelado.</p>
      ) : (
        <ol>
          {chapters.map((c) => (
            <li key={c.number} className={c.changed ? "changed" : undefined}>
              <Link to={`/novels/${novel}/v/${version}/chapters/${c.number}`}>{c.title ?? `Capítulo ${c.number}`}</Link>
              <span className="meta">
                {" "}
                · {c.words.toLocaleString("es")} palabras
              </span>
              {c.changed && <span className="mark"> · cambió en esta versión</span>}
            </li>
          ))}
        </ol>
      )}
      {run !== undefined && inProgress(run) && <p className="run-line">{describeRun(run)}</p>}
    </section>
  );
}
