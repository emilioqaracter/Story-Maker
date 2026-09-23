import { useState } from "react";
import { Link, useParams } from "react-router";

import { cacheKey } from "../commons/api/cache";
import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { useResource } from "../commons/api/resource";
import { currentVersion, useVersions } from "../commons/api/versions";
import { RequestForm } from "../commons/change-request/RequestForm";
import { Failed } from "../commons/shell/Failed";

type EntityFile = Schemas["EntityFile"];

/** MET-09 en palabras. */
const PROVENANCE: Record<string, string> = {
  brief: "del encargo",
  prose: "de la prosa",
  derived: "derivado",
  arbitration: "arbitrado",
};

/** El nombre es el primer hecho que se puede pedir cambiar (`entity.renamed`). Pura. */
export function facts(file: Pick<EntityFile, "entity" | "facts">): { attribute: string; value: string; provenance: string }[] {
  return [
    { attribute: "nombre", value: file.entity.name, provenance: "" },
    ...file.facts.map((f) => ({ attribute: f.attribute, value: f.value, provenance: PROVENANCE[f.provenance] ?? f.provenance })),
  ];
}

/** `/novels/{id}/bible/{eid}` (RF-193, RF-194): la ficha de una entidad, con «Pedir un cambio» en cada hecho. */
export function EntityCard() {
  const { id: novel = "", eid = "" } = useParams();
  const file = useResource(cacheKey(novel, 0, `entity:${eid}`), () =>
    settle(() => api.GET("/novels/{novel_id}/entities/{entity_id}", { params: { path: { novel_id: novel, entity_id: eid } } })),
  );
  const versions = useVersions(novel);
  const [asking, setAsking] = useState<string | null>(null);

  if (file.state === "loading") return <p className="loading">Cargando la ficha…</p>;
  if (file.state === "failed") return <Failed failure={file.failure} reload={file.reload} />;

  const f = file.data;
  const vigente = versions.state === "ok" ? currentVersion(versions.data.versions) : 1;
  return (
    <article className="entity-card">
      <p>
        <Link to={`/novels/${novel}/bible`}>← Personajes y lugares</Link>
      </p>
      <h1>{f.entity.name}</h1>
      <p className="hint">
        {f.entity.kind}
        {f.entity.aliases.length > 0 ? ` · también ${f.entity.aliases.join(", ")}` : ""} · canon vigente
      </p>

      <h2>Hechos</h2>
      <table className="facts-table">
        <tbody>
          {facts(f).map((h) => (
            <tr key={h.attribute}>
              <th scope="row">{h.attribute}</th>
              <td>{h.value}</td>
              <td className="meta">{h.provenance}</td>
              <td>
                <button type="button" className="link-button" onClick={() => setAsking(h.attribute)}>
                  Pedir un cambio
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {asking !== null && (
        <RequestForm
          key={asking}
          novel={novel}
          anchor={{ kind: "fact", entity_id: f.entity.entity_id, attribute: asking }}
          context={`${f.entity.name} · ${asking}`}
          onDone={() => setAsking(null)}
        />
      )}

      <h2>Relaciones</h2>
      {f.relations.length === 0 ? (
        <p>Ninguna vigente.</p>
      ) : (
        <ul>
          {f.relations.map((r) => (
            <li key={`${r.direction}-${r.kind}-${r.other_id}`}>
              {r.direction === "out" ? `${r.kind} → ` : `← ${r.kind} de `}
              <Link to={`/novels/${novel}/bible/${r.other_id}`}>{r.other_name}</Link>
              <span className="meta">
                {" "}
                · desde {r.valid_from}
                {r.valid_to ? ` hasta ${r.valid_to}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2>Dónde aparece</h2>
      {f.appearances.length === 0 ? (
        <p>En ninguna escena congelada todavía.</p>
      ) : (
        <ul>
          {f.appearances.map((a) => (
            <li key={a.scene_id}>
              <Link to={`/novels/${novel}/v/${vigente}/chapters/${a.chapter}#scene-${a.scene_id}`}>
                Capítulo {a.chapter}, escena {a.scene_number}
              </Link>
              <span className="meta"> · {a.roles.join(", ")}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
