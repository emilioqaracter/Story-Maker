import { useState, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router";

import { cacheKey } from "../commons/api/cache";
import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { useResource } from "../commons/api/resource";
import { currentVersion, useVersions } from "../commons/api/versions";
import { Failed } from "../commons/shell/Failed";
import { Empty, Loading } from "../commons/ui/State";

type Entity = Schemas["EntitySummary"];

/** Las pestanas de RF-192: personajes y lugares siempre; instituciones y objetos si los hay. */
export const TABS = [
  { kind: "person", label: "Personajes" },
  { kind: "place", label: "Lugares" },
  { kind: "institution", label: "Instituciones" },
  { kind: "object", label: "Objetos" },
] as const;

export type Kind = (typeof TABS)[number]["kind"];

/** Las pestanas que se muestran. Pura. */
export function visibleTabs(entities: readonly Pick<Entity, "kind">[]): (typeof TABS)[number][] {
  const present = new Set(entities.map((e) => e.kind));
  return TABS.filter((t) => t.kind === "person" || t.kind === "place" || present.has(t.kind));
}

/**
 * La pestana a la que lleva una tecla, con el patron de pestanas de WAI-ARIA:
 * flechas a los lados (dando la vuelta), Inicio y Fin. `null` si la tecla no es
 * de navegacion. Pura.
 */
export function tabAfterKey(key: string, current: number, count: number): number | null {
  if (count === 0) return null;
  if (key === "ArrowRight") return (current + 1) % count;
  if (key === "ArrowLeft") return (current - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

/** `/novels/{id}/bible` (RF-192, RF-195): la ficha de personajes y lugares, del canon vigente. */
export function EntityList() {
  const { id: novel = "" } = useParams();
  const entities = useResource(cacheKey(novel, 0, "entities"), () =>
    settle(() => api.GET("/novels/{novel_id}/entities", { params: { path: { novel_id: novel } } })),
  );
  const versions = useVersions(novel);
  const [tab, setTab] = useState<Kind>("person");

  if (entities.state === "loading") return <Loading>Cargando personajes y lugares…</Loading>;
  if (entities.state === "failed") return <Failed failure={entities.failure} reload={entities.reload} />;

  const vigente = versions.state === "ok" ? currentVersion(versions.data.versions) : 1;
  const rows = entities.data.entities.filter((e) => e.kind === tab);
  const tabs = visibleTabs(entities.data.entities);
  // Una sola parada de tabulador para todas las pestanas; entre ellas se va con las flechas.
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = tabAfterKey(event.key, tabs.findIndex((t) => t.kind === tab), tabs.length);
    const target = next === null ? undefined : tabs[next];
    if (target === undefined) return;
    event.preventDefault();
    setTab(target.kind);
    event.currentTarget.querySelector<HTMLButtonElement>(`#tab-${target.kind}`)?.focus();
  };
  return (
    <section className="bible">
      <h1>Personajes y lugares</h1>
      <p className="hint">La ficha refleja el canon vigente, no el del capítulo que estés leyendo.</p>
      <div className="tabs" role="tablist" aria-label="Tipo de entidad" onKeyDown={onKey}>
        {tabs.map((t) => (
          <button
            key={t.kind}
            id={`tab-${t.kind}`}
            type="button"
            role="tab"
            aria-selected={t.kind === tab}
            aria-controls="bible-panel"
            tabIndex={t.kind === tab ? 0 : -1}
            onClick={() => setTab(t.kind)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="bible-panel" aria-labelledby={`tab-${tab}`}>
        {rows.length === 0 ? (
          <Empty>No hay ninguno en esta pestaña.</Empty>
        ) : (
          <ul className="entity-list">
            {rows.map((e) => (
              <li key={e.entity_id}>
                <Link to={`/novels/${novel}/bible/${e.entity_id}`}>{e.name}</Link>
                {e.aliases.length > 0 && <span className="meta"> · también {e.aliases.join(", ")}</span>}
                {e.chapters.length > 0 && (
                  <span className="meta">
                    {" "}
                    · aparece en{" "}
                    {e.chapters.map((c, i) => (
                      <span key={c}>
                        {i > 0 && ", "}
                        <Link to={`/novels/${novel}/v/${vigente}/chapters/${c}`}>{c}</Link>
                      </span>
                    ))}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
