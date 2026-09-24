import { useParams } from "react-router";

import { api } from "../../commons/api/client";
import { settle } from "../../commons/api/errors";
import { usePolled } from "../../commons/api/poll";
import { useFollow, inFlight, type ChangeRequest } from "../../commons/change-request/follow";
import { RequestStatus } from "../../commons/change-request/RequestForm";
import { Failed } from "../../commons/shell/Failed";
import { Empty, Loading } from "../../commons/ui/State";

/**
 * `/novels/{id}/changes` (RF-189): las solicitudes de RI-48 con su estado y su
 * interpretacion. Cada una en curso se sigue con RI-49 a intervalo fijo. Solo
 * se leen: no hay ningun control que las apruebe, rechace ni fuerce (RF-191).
 */
export function Changes() {
  const { id: novel = "" } = useParams();
  // Sin cache: la lista cambia con cada solicitud nueva. Se sondea mientras haya alguna en curso.
  const list = usePolled(
    `${novel}:change-requests`,
    () => settle(() => api.GET("/novels/{novel_id}/change-requests", { params: { path: { novel_id: novel } } })),
    (data) => data.requests.some(inFlight),
  );
  if (list.state === "loading") return <Loading>Cargando las solicitudes…</Loading>;
  if (list.state === "failed") return <Failed failure={list.failure} reload={list.reload} />;
  return (
    <section className="changes">
      <h1>Solicitudes de cambio</h1>
      <p className="hint">Se piden desde la lectura, seleccionando un fragmento, o desde la ficha de un personaje o lugar.</p>
      {list.data.requests.length === 0 ? (
        <Empty>Todavía no se ha pedido ningún cambio.</Empty>
      ) : (
        <ol className="request-list">
          {[...list.data.requests].reverse().map((r) => (
            <li key={r.request_id}>
              <Row novel={novel} request={r} />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Row({ novel, request }: { novel: string; request: ChangeRequest }) {
  const followed = useFollow(novel, inFlight(request) ? request.request_id : null);
  const current = followed.state === "ok" ? followed.data : request;
  return (
    <article className="request-row">
      <p>
        <strong className="request-id">nº {current.request_id}</strong> · «{current.text}»
      </p>
      <RequestStatus novel={novel} request={current} />
    </article>
  );
}
