import { Link } from "react-router";

import { cacheKey } from "../commons/api/cache";
import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { useResource } from "../commons/api/resource";
import { NetworkError } from "../commons/shell/NetworkError";
import { layout, SIZE } from "./layout";

type ChapterSummary = Schemas["ChapterSummary"];
/** Lo que el dibujo lee del estado del mundo de RI-06. */
type World = {
  cards: readonly Pick<Schemas["EntityCard"], "entity_id" | "name" | "kind">[];
  relations?: readonly Schemas["Relation"][];
};

/** El instante en que termina el ultimo capitulo congelado. Pura. */
export function lastInstant(chapters: readonly ChapterSummary[]): { at: string; seq: number } | null {
  const last = [...chapters].sort((a, b) => a.chapter - b.chapter).at(-1);
  return last === undefined ? null : { at: last.ends_at, seq: last.ends_seq };
}

/**
 * Grafo de entidades (RF-196), en SVG a mano (D-57): las relaciones vigentes
 * del estado del mundo de RI-06 en el instante del ultimo capitulo congelado,
 * con su tipo y su vigencia. Cada nodo enlaza a su ficha. Cuando exista RI-46,
 * las relaciones saldran de ella.
 */
export function Graph({ novel }: { novel: string }) {
  const chapters = useResource(cacheKey(novel, 1, "chapters"), () =>
    settle(() => api.GET("/novels/{novel_id}/chapters", { params: { path: { novel_id: novel } } })),
  );
  const instant = chapters.state === "ok" ? lastInstant(chapters.data.chapters) : null;
  const state = useResource(instant ? cacheKey(novel, 1, `state@${instant.at}#${instant.seq}`) : null, () =>
    settle(() =>
      api.GET("/novels/{novel_id}/state", {
        params: { path: { novel_id: novel }, query: { at: instant?.at ?? "", seq: instant?.seq ?? 0 } },
      }),
    ),
  );

  let body;
  if (chapters.state === "failed" || state.state === "failed") {
    const failure = chapters.state === "failed" ? chapters.failure : state.state === "failed" ? state.failure : null;
    const reload = chapters.state === "failed" ? chapters.reload : state.reload;
    body = failure?.kind === "network" ? <NetworkError reload={reload} /> : <p className="hint">El grafo no se pudo leer.</p>;
  } else if (chapters.state === "ok" && instant === null) {
    body = <p>Sin capítulos congelados todavía: no hay instante del que dibujar el grafo.</p>;
  } else if (state.state === "ok") {
    body = <GraphSvg novel={novel} world={state.data} />;
  } else {
    body = <p className="loading">Cargando el grafo…</p>;
  }

  return (
    <section className="graph">
      <h2>Grafo de entidades</h2>
      {instant && <p className="hint">Relaciones vigentes al final del capítulo congelado más reciente ({instant.at}).</p>}
      {body}
    </section>
  );
}

function GraphSvg({ novel, world }: { novel: string; world: World }) {
  const cards = world.cards;
  const relations = world.relations ?? [];
  const names = new Map(cards.map((c) => [c.entity_id, c.name]));
  const points = layout(cards.map((c) => c.entity_id));
  if (cards.length === 0) return <p>El canon no tiene entidades todavía.</p>;

  return (
    <>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="Grafo de entidades" className="graph-svg">
        {relations.map((r) => {
          const a = points.get(r.source_id);
          const b = points.get(r.target_id);
          if (!a || !b) return null;
          return (
            <g key={`${r.source_id}-${r.kind}-${r.target_id}-${r.valid_from}`} className="edge">
              <title>{`${names.get(r.source_id) ?? r.source_id} · ${r.kind} · ${names.get(r.target_id) ?? r.target_id}, desde ${r.valid_from}${r.valid_to ? ` hasta ${r.valid_to}` : ""}`}</title>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} className="edge-label">
                {r.kind}
              </text>
            </g>
          );
        })}
        {cards.map((c) => {
          const p = points.get(c.entity_id);
          if (!p) return null;
          return (
            <Link key={c.entity_id} to={`/novels/${novel}/bible/${c.entity_id}`} className="node">
              <title>{`${c.name} · ${c.kind}`}</title>
              <circle cx={p.x} cy={p.y} r={10} />
              <text x={p.x} y={p.y + 26} textAnchor="middle">
                {c.name}
              </text>
            </Link>
          );
        })}
      </svg>
      <table className="relations">
        <caption>Relaciones vigentes</caption>
        <thead>
          <tr>
            <th>De</th>
            <th>Relación</th>
            <th>A</th>
            <th>Vigencia</th>
          </tr>
        </thead>
        <tbody>
          {relations.length === 0 ? (
            <tr>
              <td colSpan={4}>Ninguna relación vigente en este instante.</td>
            </tr>
          ) : (
            relations.map((r) => (
              <tr key={`${r.source_id}-${r.kind}-${r.target_id}-${r.valid_from}`}>
                <td>{names.get(r.source_id) ?? r.source_id}</td>
                <td>{r.kind}</td>
                <td>{names.get(r.target_id) ?? r.target_id}</td>
                <td>
                  desde {r.valid_from}
                  {r.valid_to ? ` hasta ${r.valid_to}` : ""}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </>
  );
}
