import { useCallback, useEffect, useRef, useState } from "react";

import type { Failure, Outcome } from "./errors";
import type { Loaded } from "./resource";

/**
 * Intervalo de sondeo del estado (D-59). **Propuesta**: 5 segundos, el orden de
 * duracion de una llamada de modelo; se ajusta al medir. Vive solo aqui.
 */
export const POLL_MS = 5_000;

/**
 * Pide `load` ahora y cada `POLL_MS` mientras `keepGoing` diga que si.
 *
 * Solo lee: el sondeo sigue el estado, no lo cambia. Un fallo de red no para el
 * sondeo; se muestra, y la siguiente vuelta lo vuelve a intentar.
 */
export function usePolled<T>(
  key: string | null,
  load: () => Promise<Outcome<T>>,
  keepGoing: (data: T) => boolean,
): Loaded<T> & { reload: () => void } {
  const [value, setValue] = useState<{ key: string; loaded: Loaded<T> } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const loader = useRef(load);
  loader.current = load;
  const continues = useRef(keepGoing);
  continues.current = keepGoing;

  useEffect(() => {
    if (key === null) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async (): Promise<void> => {
      const outcome = await loader.current();
      if (!live) return;
      if (outcome.ok) {
        setValue({ key, loaded: { state: "ok", data: outcome.data } });
        if (!continues.current(outcome.data)) return;
      } else {
        const failure: Failure = outcome.failure;
        setValue((old) =>
          old !== null && old.key === key && old.loaded.state === "ok" && failure.kind === "network"
            ? old
            : { key, loaded: { state: "failed", failure } },
        );
        if (failure.kind === "not-found") return;
      }
      timer = setTimeout(() => void tick(), POLL_MS);
    };
    void tick();
    return () => {
      live = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  if (value === null || value.key !== key) return { state: "loading", reload };
  return { ...value.loaded, reload };
}
