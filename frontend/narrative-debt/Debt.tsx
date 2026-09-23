import { cacheKey } from "../commons/api/cache";
import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { useResource } from "../commons/api/resource";
import { NetworkError } from "../commons/shell/NetworkError";

type Setup = Schemas["SetupStatus"];

/**
 * Deuda narrativa (RF-197): los setups abiertos de RI-07 con su estado. No
 * calcula nada; la deuda es la que el backend sirve (CAN-08).
 */
export function Debt({ novel }: { novel: string }) {
  const debt = useResource(cacheKey(novel, 1, "debt"), () =>
    settle(() => api.GET("/novels/{novel_id}/debt", { params: { path: { novel_id: novel } } })),
  );

  return (
    <section className="debt">
      <h2>Deuda narrativa</h2>
      {debt.state === "loading" && <p className="loading">Cargando la deuda…</p>}
      {debt.state === "failed" &&
        (debt.failure.kind === "network" ? (
          <NetworkError reload={debt.reload} />
        ) : (
          <p className="hint">{debt.failure.kind === "not-found" && debt.failure.detail ? debt.failure.detail : "La deuda no se pudo leer."}</p>
        ))}
      {debt.state === "ok" && (
        <>
          <p>
            {debt.data.open_setups.length} setups abiertos sin payoff · {debt.data.planned.length} previstos sin
            plantar · {(debt.data.paid ?? []).length} cobrados
          </p>
          {debt.data.open_setups.length > 0 && <SetupList setups={debt.data.open_setups} />}
        </>
      )}
    </section>
  );
}

function SetupList({ setups }: { setups: readonly Setup[] }) {
  return (
    <ul className="setups">
      {setups.map((s) => (
        <li key={s.id}>
          <strong>{s.description}</strong>
          <span className="meta">
            {" "}
            · {s.state} en el capítulo {s.planted_chapter ?? "—"}, escena {s.planted_scene} · payoff previsto en el
            capítulo {s.payoff_chapter ?? "—"}, escena {s.payoff_scene}
          </span>
        </li>
      ))}
    </ul>
  );
}
