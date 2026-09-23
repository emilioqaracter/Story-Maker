import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";

import { api, type Schemas } from "../commons/api/client";
import { settle, type Failure } from "../commons/api/errors";
import { Failed } from "../commons/shell/Failed";
import { rememberInterview, rememberNovel } from "../commons/storage/local";
import { Prose } from "../commons/text/Prose";
import { fieldId, PANEL, shown, type FieldName } from "./panel";

type Turn = Schemas["TurnIn"];

function fetchState(iid: string) {
  return settle(() => api.GET("/interviews/{interview_id}", { params: { path: { interview_id: iid } } }));
}
/** El estado tal como lo tipa el cliente generado (RD-31). */
type State = Extract<Awaited<ReturnType<typeof fetchState>>, { ok: true }>["data"];

/**
 * `/interviews/{iid}` (RF-167 a RF-176). Todo lo que se ve es el estado que el
 * backend devolvio en el ultimo turno: el frontend no guarda un borrador propio
 * ni decide que falta.
 */
export function Interview() {
  const { iid = "" } = useParams();
  const [state, setState] = useState<State | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [sending, setSending] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    void fetchState(iid).then((o) => {
      if (!live) return;
      if (o.ok) {
        setState(o.data);
        rememberInterview(iid);
      } else setFailure(o.failure);
    });
    return () => {
      live = false;
    };
  }, [iid, attempt]);

  const send = useCallback(
    async (turn: Turn): Promise<boolean> => {
      setSending(true);
      const o = await settle(() =>
        api.POST("/interviews/{interview_id}/turns", { params: { path: { interview_id: iid } }, body: turn }),
      );
      setSending(false);
      if (o.ok) {
        setState(o.data);
        return true;
      }
      setFailure(o.failure);
      return false;
    },
    [iid],
  );

  if (failure) return <Failed failure={failure} reload={() => (setFailure(null), setAttempt((n) => n + 1))} />;
  if (state === null) return <p className="loading">Cargando la entrevista…</p>;

  return (
    <section className="interview">
      <div className="conversation">
        <h1>El encargo</h1>
        <Conversation state={state} />
        <Answer key={state.question?.field ?? "fin"} state={state} sending={sending} send={send} />
        <FreeText sending={sending} send={send} />
        <Proposed state={state} sending={sending} send={send} />
      </div>
      <aside className="brief-panel" aria-label="El brief">
        <BriefPanel state={state} sending={sending} send={send} />
        <Create state={state} />
      </aside>
    </section>
  );
}

function Conversation({ state }: { state: State }) {
  return (
    <ol className="messages">
      {state.messages.map((m, i) => (
        <li key={i} className={`message ${m.role} ${m.kind}`}>
          {m.kind === "free_text" ? (
            <details>
              <summary>Texto libre pegado ({m.text.length} caracteres)</summary>
              <Prose text={m.text} />
            </details>
          ) : (
            m.text
          )}
        </li>
      ))}
    </ol>
  );
}

type Send = (turn: Turn) => Promise<boolean>;

function Answer({ state, sending, send }: { state: State; sending: boolean; send: Send }) {
  const [text, setText] = useState("");
  if (state.question === null) return null;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (text.trim() && (await send({ answer: text }))) setText("");
  };
  return (
    <form onSubmit={submit} className="answer">
      <label>
        Tu respuesta
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} aria-label="Tu respuesta" />
      </label>
      <button type="submit" disabled={sending || !text.trim()}>
        Responder
      </button>
    </form>
  );
}

/** RF-173. Texto no confiable: viaja como tal y nunca se pinta en el panel del brief. */
function FreeText({ sending, send }: { sending: boolean; send: Send }) {
  const [text, setText] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (text.trim() && (await send({ free_text: text }))) setText("");
  };
  return (
    <form onSubmit={submit} className="free-text">
      <label>
        Texto libre: una anécdota, una carta, recuerdos
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} aria-label="Texto libre" />
      </label>
      <p className="hint">El sistema propone hechos sacados de este texto, cada uno con su cita. Solo entran los que aceptes.</p>
      <button type="submit" disabled={sending || !text.trim()}>
        Enviar el texto
      </button>
    </form>
  );
}

/** RF-174. Cada hecho propuesto con su cita; aceptar o descartar viaja en el turno. */
function Proposed({ state, sending, send }: { state: State; sending: boolean; send: Send }) {
  const pending = state.proposed.filter((p) => p.status === "proposed");
  if (state.proposed.length === 0) return null;
  const label: Record<string, string> = {
    "recipient.traits": "Rasgo",
    "recipient.memories": "Recuerdo",
    "entity.person": "Persona",
    "entity.place": "Lugar",
  };
  return (
    <section className="proposed">
      <h2>Hechos propuestos</h2>
      {state.discarded_quotes > 0 && (
        <p className="hint">Se descartaron {state.discarded_quotes} porque su cita no aparece tal cual en el texto.</p>
      )}
      <ul>
        {state.proposed.map((p) => (
          <li key={p.fact_id} className={p.status}>
            <strong>{label[p.target] ?? p.target}:</strong> {p.value}
            <blockquote>«{p.quote}»</blockquote>
            {p.status === "proposed" ? (
              <span className="actions">
                <button type="button" disabled={sending} onClick={() => void send({ accept: [p.fact_id] })}>
                  Aceptar
                </button>
                <button type="button" disabled={sending} onClick={() => void send({ discard: [p.fact_id] })}>
                  Descartar
                </button>
              </span>
            ) : (
              <span className="meta"> · {p.status === "accepted" ? "aceptado" : "descartado"}</span>
            )}
          </li>
        ))}
      </ul>
      {pending.length === 0 && <p className="hint">No queda ninguno por decidir.</p>}
    </section>
  );
}

/** RF-169 a RF-172. El panel es proyeccion del estado; editar un campo es un turno. */
function BriefPanel({ state, sending, send }: { state: State; sending: boolean; send: Send }) {
  const faltan = new Set(state.missing.map((m) => m.field));
  const choque = new Set(state.contradictions.flatMap((c) => c.fields));
  return (
    <>
      <h2>El brief</h2>
      <dl className="brief-fields">
        {PANEL.map((f) => (
          <Field
            key={`${f.field}:${shown(state.draft, f.field)}`}
            field={f.field}
            label={f.label}
            long={f.long === true}
            value={shown(state.draft, f.field)}
            missing={faltan.has(f.field)}
            conflict={choque.has(f.field)}
            sending={sending}
            send={send}
          />
        ))}
      </dl>
      {(state.draft.entities ?? []).length > 0 && (
        <>
          <h3>Personajes y lugares aceptados</h3>
          <ul>
            {(state.draft.entities ?? []).map((e) => (
              <li key={`${e.kind}:${e.name}`}>
                {e.name} <span className="meta">· {e.kind === "person" ? "persona" : "lugar"}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {state.missing.length > 0 && (
        <section className="missing">
          <h3>Falta</h3>
          <ul>
            {state.missing.map((m) => (
              <li key={m.field}>
                <a href={`#${fieldId(m.field as FieldName)}`}>{m.label}</a>
              </li>
            ))}
          </ul>
        </section>
      )}
      {state.contradictions.length > 0 && (
        <section className="contradictions" role="alert">
          <h3>No encaja</h3>
          <ul>
            {state.contradictions.map((c, i) => (
              <li key={i}>
                {c.message}{" "}
                <span className="meta">
                  (regla {c.rule}:{" "}
                  {c.fields.map((f, j) => (
                    <span key={f}>
                      {j > 0 && " · "}
                      <a href={`#${fieldId(f as FieldName)}`}>{f}</a>
                    </span>
                  ))}
                  )
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function Field(props: {
  field: FieldName;
  label: string;
  long: boolean;
  value: string;
  missing: boolean;
  conflict: boolean;
  sending: boolean;
  send: Send;
}) {
  const [draft, setDraft] = useState(props.value);
  const dirty = draft !== props.value;
  const save = (e: FormEvent) => {
    e.preventDefault();
    if (dirty) void props.send({ edits: [{ field: props.field, value: draft }] });
  };
  const cls = ["field", props.missing ? "missing" : "", props.conflict ? "conflict" : ""].join(" ").trim();
  return (
    <div className={cls} id={fieldId(props.field)}>
      <dt>
        {props.label}
        {props.missing && <span className="mark"> · falta</span>}
      </dt>
      <dd>
        <form onSubmit={save}>
          {props.long ? (
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2} aria-label={props.label} />
          ) : (
            <input value={draft} onChange={(e) => setDraft(e.target.value)} aria-label={props.label} />
          )}
          {dirty && (
            <button type="submit" disabled={props.sending}>
              Guardar
            </button>
          )}
        </form>
      </dd>
    </div>
  );
}

/** RF-175, RF-176. Solo con el brief completo. Sin «saltar» ni «crear igual». */
function Create({ state }: { state: State }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const ready = state.complete && state.brief != null && state.novel_id != null;

  const create = async () => {
    if (!state.brief || !state.novel_id) return;
    const novel = state.novel_id;
    setBusy(true);
    setProblems([]);
    const created = await settle(() => api.POST("/novels", { params: { query: { novel_id: novel } }, body: state.brief! }));
    if (!created.ok) {
      setBusy(false);
      setProblems(rejection(created.failure));
      return;
    }
    rememberNovel(novel);
    await settle(() => api.POST("/novels/{novel_id}/run", { params: { path: { novel_id: novel } } }));
    void navigate(`/novels/${novel}`);
  };

  return (
    <div className="create">
      <button type="button" onClick={() => void create()} disabled={!ready || busy}>
        {busy ? "Creando…" : "Crear y escribir"}
      </button>
      {!ready && <p className="hint">Se habilita cuando el brief está completo y no hay nada que no encaje.</p>}
      {problems.length > 0 && (
        <ul role="alert" className="contradictions">
          {problems.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Lo que RI-01 dijo al rechazar, en palabras (RI-41). Pura. */
export function rejection(failure: Failure): string[] {
  if (failure.kind === "network") return ["No se pudo hablar con el backend."];
  if (failure.kind === "server") return [`El backend respondió ${failure.status}${failure.detail ? `: ${failure.detail}` : ""}.`];
  return [failure.detail || "El backend rechazó el brief."];
}
