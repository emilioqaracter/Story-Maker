import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { cache } from "./cache";
import type { Failure, Outcome } from "./errors";

export type Loaded<T> =
  | { state: "loading" }
  | { state: "ok"; data: T }
  | { state: "failed"; failure: Failure };

/**
 * Lee una respuesta cacheada por clave (RD-28), o la pide si no esta.
 *
 * Un fallo no se cachea: se muestra y se puede repetir la lectura (RF-164).
 * `key` nula significa «todavia no hay que pedir nada».
 *
 * Cuando la cache de una novela se suelta, lo que ya se estaba mostrando con
 * esa misma clave sigue en pantalla mientras se vuelve a pedir: la lectura no
 * cambia bajo los pies ni pierde lo que el lector tenia abierto (RF-190).
 */
export function useResource<T>(key: string | null, load: () => Promise<Outcome<T>>): Loaded<T> & { reload: () => void } {
  const cached = useSyncExternalStore(cache.subscribe, () => (key === null ? undefined : cache.get(key)));
  const [failure, setFailure] = useState<{ key: string; failure: Failure } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const loader = useRef(load);
  loader.current = load;
  const last = useRef<{ key: string; data: unknown } | null>(null);
  if (key !== null && cached !== undefined) last.current = { key, data: cached };
  const missing = key !== null && cached === undefined;

  useEffect(() => {
    if (!missing || key === null) return;
    let live = true;
    void loader.current().then((outcome) => {
      if (!live) return;
      if (outcome.ok) {
        setFailure(null);
        cache.set(key, outcome.data);
      } else {
        setFailure({ key, failure: outcome.failure });
      }
    });
    return () => {
      live = false;
    };
  }, [key, missing, attempt]);

  const reload = useCallback(() => {
    setFailure(null);
    setAttempt((n) => n + 1);
  }, []);

  if (key !== null && cached !== undefined) return { state: "ok", data: cached as T, reload };
  if (key !== null && last.current?.key === key) return { state: "ok", data: last.current.data as T, reload };
  if (failure !== null && failure.key === key) return { state: "failed", failure: failure.failure, reload };
  return { state: "loading", reload };
}
