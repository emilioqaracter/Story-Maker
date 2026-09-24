import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { usePolled } from "../commons/api/poll";
import { describeRun, inProgress, useRunState, type RunState } from "../commons/api/run-state";
import { Failed } from "../commons/shell/Failed";
import { Empty, Loading } from "../commons/ui/State";

/** Cuantos registros de la traza se muestran: los ultimos. Es tamano de pantalla, no umbral. */
export const TRACE_ROWS = 50;

type TraceRecord = Schemas["TraceRecord"];

/**
 * Estado de la tirada (RI-03) y ultimos registros de la traza (RI-27), en
 * lectura (RF-198). Se sondea mientras la obra no este cerrada (D-59).
 * No tiene controles: ni «continuar», ni «reintentar», ni «forzar» (RF-199).
 */
export function Status({ novel }: { novel: string }) {
  const run = useRunState(novel);
  const running = run.state === "ok" && inProgress(run.data);
  const trace = usePolled(
    run.state === "ok" ? `${novel}:trace` : null,
    () =>
      settle(() =>
        api.GET("/novels/{novel_id}/trace", { params: { path: { novel_id: novel }, query: { limit: TRACE_ROWS } } }),
      ),
    () => running,
  );

  if (run.state === "loading") return <Loading>Cargando el estado…</Loading>;
  if (run.state === "failed") return <Failed failure={run.failure} reload={run.reload} />;

  return (
    <section className="status">
      <h2>Estado de la tirada</h2>
      <p className={run.data.running ? "run-line running" : "run-line"}>{describeRun(run.data)}</p>
      <RunFacts state={run.data} />
      <h3>Últimos registros de la traza</h3>
      {trace.state === "ok" ? (
        <TraceTable records={trace.data.records} />
      ) : trace.state === "failed" ? (
        <p className="hint">La traza no se pudo leer.</p>
      ) : (
        <Loading>Cargando la traza…</Loading>
      )}
    </section>
  );
}

function RunFacts({ state }: { state: RunState }) {
  const cierre = state.closed === true ? "Cerrada" : state.closed === false ? "Sin cerrar" : "Pendiente";
  return (
    <dl className="facts">
      <div>
        <dt>En marcha</dt>
        <dd>{state.running ? "Sí" : "No"}</dd>
      </div>
      <div>
        <dt>Capítulo en curso</dt>
        <dd>{state.chapter_in_progress ?? "—"}</dd>
      </div>
      <div>
        <dt>Última escena cerrada</dt>
        <dd>{state.last_closed_scene ?? "—"}</dd>
      </div>
      <div>
        <dt>Capítulos congelados</dt>
        <dd>{state.frozen_chapters}</dd>
      </div>
      <div>
        <dt>Cuarentenas</dt>
        <dd>{state.quarantines}</dd>
      </div>
      <div>
        <dt>Condición de cierre</dt>
        <dd>
          {cierre}
          {state.reason ? ` · ${state.reason}` : ""}
        </dd>
      </div>
    </dl>
  );
}

/** Los campos de un registro, como texto: son datos, no marcado (RI-53). Pura. */
export function fieldsText(record: TraceRecord): string {
  const fields = record.fields ?? {};
  return Object.entries(fields)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" · ");
}

function TraceTable({ records }: { records: readonly TraceRecord[] }) {
  if (records.length === 0) return <Empty>La traza está vacía.</Empty>;
  return (
    <div className="table-scroll">
      <table className="trace">
        <thead>
          <tr>
            <th>#</th>
            <th>Instante</th>
            <th>Tipo</th>
            <th>Campos</th>
          </tr>
        </thead>
        <tbody>
          {[...records].reverse().map((r) => (
            <tr key={r.seq}>
              <td>{r.seq}</td>
              <td>{r.at}</td>
              <td>{r.kind}</td>
              <td className="fields">{fieldsText(r)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
