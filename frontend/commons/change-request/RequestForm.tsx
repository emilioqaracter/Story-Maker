import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, type Schemas } from "../api/client";
import { settle } from "../api/errors";
import { inFlight, useFollow, type ChangeRequest } from "./follow";

export type Anchor = Schemas["FragmentAnchor"] | Schemas["FactAnchor"];

/**
 * «Pedir un cambio» (RF-187, RF-194). La peticion y su ancla van a RI-47; la
 * respuesta se muestra al instante (RF-188). Si el sistema no la entiende, la
 * rechaza con su motivo y el campo queda para reformular: el frontend nunca
 * elige entre interpretaciones (RI-52). Lo unico que se puede hacer con una
 * solicitud es crearla y leerla (RF-191): ni aprobarla, ni forzarla.
 */
export function RequestForm({
  novel,
  anchor,
  context,
  onDone,
}: {
  novel: string;
  anchor: Anchor;
  context: string;
  onDone?: () => void;
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [request, setRequest] = useState<ChangeRequest | null>(null);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    const outcome = await settle(() =>
      api.POST("/novels/{novel_id}/change-requests", {
        params: { path: { novel_id: novel } },
        body: { text, anchor },
      }),
    );
    setSending(false);
    if (outcome.ok) setRequest(outcome.data);
    else setError(outcome.failure.kind === "network" ? "No se pudo hablar con el backend." : "El backend no aceptó la petición.");
  };

  return (
    <div className="request-form">
      <p className="hint">Sobre: {context}</p>
      {request === null || request.status === "rejected" ? (
        <form onSubmit={send}>
          <label>
            {request?.status === "rejected" ? "Reformula la petición" : "¿Qué quieres cambiar?"}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="Por ejemplo: el perro se llama Nala"
            />
          </label>
          <button type="submit" disabled={sending || !text.trim()}>
            {sending ? "Enviando…" : "Pedir el cambio"}
          </button>
          {onDone && (
            <button type="button" onClick={onDone}>
              Cerrar
            </button>
          )}
        </form>
      ) : null}
      {error && <p role="alert">{error}</p>}
      {request && <Response novel={novel} request={request} />}
    </div>
  );
}

/** La respuesta de RI-47 y su seguimiento (RF-188 a RF-190). */
export function Response({ novel, request }: { novel: string; request: ChangeRequest }) {
  const followed = useFollow(novel, inFlight(request) ? request.request_id : null);
  const current = followed.state === "ok" ? followed.data : request;
  return <RequestStatus novel={novel} request={current} />;
}

export function RequestStatus({ novel, request }: { novel: string; request: ChangeRequest }) {
  const i = request.interpretation;
  const interpretation = i ? (
    <p>
      Entendido: <strong>{i.entity_id}</strong> · {i.attribute}: «{i.previous_value}» → «{i.new_value}»
    </p>
  ) : null;
  if (request.status === "rejected") {
    return (
      <div className="request-status rejected" role="status">
        <p>No se aplicará: {request.reason}</p>
      </div>
    );
  }
  if (request.status === "applied") {
    const first = request.changed_chapters[0];
    return (
      <div className="request-status applied" role="status">
        {interpretation}
        <p>
          Aplicado: versión {request.version} lista
          {request.changed_chapters.length > 0
            ? `, cambiaron los capítulos ${request.changed_chapters.join(", ")}.`
            : ", sin capítulos que cambiar."}
        </p>
        {first !== undefined && request.version != null && (
          <Link to={`/novels/${novel}/v/${request.version}/chapters/${first}`}>
            Leer el capítulo {first} en la versión {request.version}
          </Link>
        )}
      </div>
    );
  }
  return (
    <div className="request-status queued" role="status">
      {interpretation}
      <p>{request.status === "applying" ? "Aplicándose…" : "En cola: se aplicará en cuanto el sistema pueda."}</p>
    </div>
  );
}
