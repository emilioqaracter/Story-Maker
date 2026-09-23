import type { Failure } from "../api/errors";
import { NetworkError } from "./NetworkError";
import { NotFound } from "./NotFound";

/** La pantalla que corresponde a un fallo de lectura (RF-164). */
export function Failed({ failure, reload }: { failure: Failure; reload: () => void }) {
  if (failure.kind === "not-found") return <NotFound detail={failure.detail} />;
  if (failure.kind === "network") return <NetworkError reload={reload} />;
  return (
    <section className="notice" role="alert">
      <h2>El backend respondió con un error</h2>
      <p>
        Estado {failure.status}
        {failure.detail ? `: ${failure.detail}` : "."}
      </p>
      <button type="button" onClick={reload}>
        Volver a cargar
      </button>
    </section>
  );
}
