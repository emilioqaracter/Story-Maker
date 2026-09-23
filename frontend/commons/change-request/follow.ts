import { useEffect, useRef } from "react";

import { cache } from "../api/cache";
import { api, type Schemas } from "../api/client";
import { settle } from "../api/errors";
import { usePolled } from "../api/poll";

export type ChangeRequest = Schemas["ChangeRequest"];

/** Mientras no este aplicada ni rechazada, el backend la esta trabajando (RI-51). Pura. */
export function inFlight(request: Pick<ChangeRequest, "status">): boolean {
  return request.status === "queued" || request.status === "applying";
}

/**
 * Sigue una solicitud con RI-49 a intervalo fijo (D-59) hasta que sea
 * `applied` o `rejected` (RF-189). Solo lee: ninguna transicion sale de aqui.
 * Al aplicarse suelta la cache de la novela, porque hay una version nueva
 * (RF-190, RD-28), y avisa una sola vez.
 */
export function useFollow(novel: string, requestId: number | null, onApplied?: (r: ChangeRequest) => void) {
  const polled = usePolled(
    requestId === null ? null : `${novel}:request:${requestId}`,
    () =>
      settle(() =>
        api.GET("/novels/{novel_id}/change-requests/{request_id}", {
          params: { path: { novel_id: novel, request_id: requestId ?? 0 } },
        }),
      ),
    inFlight,
  );
  const announced = useRef<number | null>(null);
  const callback = useRef(onApplied);
  callback.current = onApplied;

  useEffect(() => {
    if (polled.state !== "ok" || polled.data.status !== "applied") return;
    if (announced.current === polled.data.request_id) return;
    announced.current = polled.data.request_id;
    cache.invalidateNovel(novel);
    callback.current?.(polled.data);
  }, [polled, novel]);

  return polled;
}
