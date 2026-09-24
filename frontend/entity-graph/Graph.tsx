import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Link } from "react-router";

import { cacheKey } from "../commons/api/cache";
import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { useResource } from "../commons/api/resource";
import { NetworkError } from "../commons/shell/NetworkError";
import { Empty, Loading } from "../commons/ui/State";
import { layout3d, project, rotate } from "./layout3d";

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
 * Grafo de entidades (RF-196), en 3D y en SVG a mano (`srs-frontend-v2.md` RF-282,
 * D-118; D-57): las relaciones vigentes del estado del mundo de RI-06 en el
 * instante del ultimo capitulo congelado, con su tipo y su vigencia. Cada nodo
 * enlaza a su ficha. Cuando exista RI-46, las relaciones saldran de ella.
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
    body = <Empty>Sin capítulos congelados todavía: no hay instante del que dibujar el grafo.</Empty>;
  } else if (state.state === "ok") {
    body = <GraphSvg novel={novel} world={state.data} />;
  } else {
    body = <Loading>Cargando el grafo…</Loading>;
  }

  return (
    <section className="graph">
      <h2>Grafo de entidades</h2>
      {instant && <p className="hint">Relaciones vigentes al final del capítulo congelado más reciente ({instant.at}).</p>}
      {body}
    </section>
  );
}

/** Lado del lienzo y radio de la esfera, en unidades del `viewBox`. */
const SIZE = 520;
const RADIUS = 170;
/** Orientacion de partida: un poco desde arriba, para que se lea la profundidad. */
const START = { yaw: 0.55, pitch: -0.32 };
const PITCH_LIMIT = 1.2;
/** Radianes por segundo del giro automatico: una vuelta en algo mas de un minuto (RNF-61). */
const SPIN = 0.09;

type Kind = "person" | "place" | "other";

/** El grupo de una entidad para su tono y su leyenda. El tipo es texto libre del canon. Pura. */
export function kindGroup(kind: string): Kind {
  const k = kind.toLowerCase();
  if (/^(person|character|personaje|persona)/.test(k)) return "person";
  if (/^(place|location|lugar)/.test(k)) return "place";
  return "other";
}

const LEGEND: Record<Kind, string> = { person: "Personajes", place: "Lugares", other: "Otras entidades" };

/** Si quien mira acepta movimiento. Sin `matchMedia`, como en jsdom, se asume que no: nada se mueve solo (RNF-61). */
export function motionAllowed(): boolean {
  return typeof window.matchMedia === "function" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Lo de delante, entero; lo del fondo, atenuado hasta un 35 %. */
function fade(depth: number): number {
  return 0.35 + 0.65 * ((depth + 1) / 2);
}

/** Ecuador y meridiano de la esfera, como guia de profundidad: 48 puntos cada uno. */
const RINGS = [0, 1].map((axis) =>
  Array.from({ length: 49 }, (_, i) => {
    const t = (2 * Math.PI * i) / 48;
    return axis === 0 ? { x: Math.cos(t), y: 0, z: Math.sin(t) } : { x: Math.cos(t), y: Math.sin(t), z: 0 };
  }),
);

const KEYS: Record<string, [number, number]> = {
  ArrowLeft: [-0.2, 0],
  ArrowRight: [0.2, 0],
  ArrowUp: [0, -0.15],
  ArrowDown: [0, 0.15],
};

function GraphSvg({ novel, world }: { novel: string; world: World }) {
  const cards = world.cards;
  const relations = useMemo(() => world.relations ?? [], [world.relations]);
  const points = useMemo(
    () =>
      layout3d(
        cards.map((c) => c.entity_id),
        relations.map((r) => [r.source_id, r.target_id] as const),
      ),
    [cards, relations],
  );
  const [angle, setAngle] = useState(START);
  const [touched, setTouched] = useState(false);
  const [paused, setPaused] = useState(false);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");

  // El giro lento, solo si quien mira acepta movimiento, hasta que toca el grafo y en pausa mientras lo apunta (RNF-61).
  useEffect(() => {
    if (touched || paused || !motionAllowed() || typeof requestAnimationFrame !== "function") return;
    let frame = 0;
    let last: number | null = null;
    const tick = (now: number) => {
      if (last !== null) {
        const dt = Math.min((now - last) / 1000, 0.1);
        setAngle((a) => ({ ...a, yaw: a.yaw + SPIN * dt }));
      }
      last = now;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [touched, paused]);

  if (cards.length === 0) return <Empty>El canon no tiene entidades todavía.</Empty>;

  const names = new Map(cards.map((c) => [c.entity_id, c.name]));
  const turn = (dyaw: number, dpitch: number) =>
    setAngle((a) => ({ yaw: a.yaw + dyaw, pitch: Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, a.pitch + dpitch)) }));

  const onKeyDown = (event: KeyboardEvent) => {
    const delta = KEYS[event.key];
    if (!delta) return;
    event.preventDefault();
    setTouched(true);
    turn(delta[0], delta[1]);
  };
  const onPointerDown = (event: PointerEvent) => {
    drag.current = { x: event.clientX, y: event.clientY, moved: false };
  };
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const dx = event.clientX - d.x;
    const dy = event.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) < 4) return;
    if (!d.moved) event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, moved: true };
    setTouched(true);
    turn(dx * 0.008, dy * 0.008);
  };
  // El clic que cierra un arrastre no abre la ficha: la captura de clic lo descarta antes de soltar el estado.
  const onPointerUp = () => {
    const d = drag.current;
    if (d && !d.moved) drag.current = null;
    else if (d) queueMicrotask(() => (drag.current = null));
  };

  const placed = cards.flatMap((c) => {
    const p = points.get(c.entity_id);
    return p ? [{ card: c, at: project(rotate(p, angle.yaw, angle.pitch), SIZE, RADIUS) }] : [];
  });
  const at = new Map(placed.map((n) => [n.card.entity_id, n.at]));
  // Lo de atras se pinta primero: el SVG no tiene profundidad propia.
  const nodes = [...placed].sort((a, b) => a.at.depth - b.at.depth);
  const edges = relations
    .flatMap((r) => {
      const a = at.get(r.source_id);
      const b = at.get(r.target_id);
      return a && b ? [{ r, a, b, depth: (a.depth + b.depth) / 2 }] : [];
    })
    .sort((e, f) => e.depth - f.depth);
  const groups = [...new Set(cards.map((c) => kindGroup(c.kind)))].sort();
  const rings = RINGS.map((ring) =>
    ring
      .map((q, i) => {
        const p = project(rotate(q, angle.yaw, angle.pitch), SIZE, RADIUS);
        return `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
      })
      .join(" "),
  );

  return (
    <>
    <div
      className="graph-stage"
      tabIndex={0}
      onKeyDown={onKeyDown}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      aria-describedby={`${uid}-ayuda`}
    >
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label="Grafo de entidades"
        className="graph-svg graph-3d"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClickCapture={(event) => {
          if (drag.current?.moved) event.preventDefault();
        }}
      >
        <defs>
          {(["person", "place", "other"] as const).map((k) => (
            <radialGradient key={k} id={`${uid}-${k}`} cx="35%" cy="30%" r="75%">
              <stop offset="0%" className={`sphere-hi sphere-${k}`} />
              <stop offset="45%" className={`sphere-mid sphere-${k}`} />
              <stop offset="100%" className={`sphere-lo sphere-${k}`} />
            </radialGradient>
          ))}
          <radialGradient id={`${uid}-floor`}>
            <stop offset="0%" className="floor-in" />
            <stop offset="100%" className="floor-out" />
          </radialGradient>
        </defs>
        <ellipse cx={SIZE / 2} cy={SIZE / 2 + RADIUS * 1.3} rx={RADIUS * 1.15} ry={RADIUS * 0.16} fill={`url(#${uid}-floor)`} />
        {rings.map((d, i) => (
          <path key={i} d={d} className="graph-ring" />
        ))}
        {edges.map(({ r, a, b, depth }) => (
          <g key={`${r.source_id}-${r.kind}-${r.target_id}-${r.valid_from}`} className="edge" style={{ opacity: fade(depth) }}>
            <title>{`${names.get(r.source_id) ?? r.source_id} · ${r.kind} · ${names.get(r.target_id) ?? r.target_id}, desde ${r.valid_from}${r.valid_to ? ` hasta ${r.valid_to}` : ""}`}</title>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} style={{ strokeWidth: 1.4 + depth * 0.6 }} />
            <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 5} className="edge-label">
              {r.kind}
            </text>
          </g>
        ))}
        {nodes.map(({ card: c, at: p }) => {
          const r = 16 * p.scale;
          const group = kindGroup(c.kind);
          return (
            <Link
              key={c.entity_id}
              to={`/novels/${novel}/bible/${c.entity_id}`}
              className={`node node-${group}`}
              style={{ opacity: fade(p.depth) }}
            >
              <title>{`${c.name} · ${c.kind}`}</title>
              <ellipse cx={p.x + r * 0.3} cy={p.y + r * 1.05} rx={r * 0.85} ry={r * 0.26} className="node-shadow" />
              <circle cx={p.x} cy={p.y} r={r} fill={`url(#${uid}-${group})`} />
              <text x={p.x} y={p.y + r + 15 * p.scale} textAnchor="middle" style={{ fontSize: `${13 * p.scale}px` }}>
                {c.name}
              </text>
            </Link>
          );
        })}
      </svg>
      <p className="hint graph-help" id={`${uid}-ayuda`}>
        Arrastra el grafo o usa las flechas del teclado para girarlo.
      </p>
      <ul className="graph-legend" aria-label="Leyenda">
        {groups.map((g) => (
          <li key={g} className={`legend-${g}`}>
            {LEGEND[g]}
          </li>
        ))}
      </ul>
    </div>
    <Relations relations={relations} names={names} />
    </>
  );
}

function Relations({ relations, names }: { relations: readonly Schemas["Relation"][]; names: Map<string, string> }) {
  return (
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
  );
}
