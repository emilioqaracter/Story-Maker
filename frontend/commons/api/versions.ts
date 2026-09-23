import { cacheKey } from "./cache";
import { api, type Schemas } from "./client";
import { settle } from "./errors";
import { useResource } from "./resource";

export type VersionInfo = Schemas["VersionInfo"];

/**
 * Las versiones de una novela (RI-42, PRO-08). Lo usan la lectura, la ficha y
 * las solicitudes: todas enlazan a la version vigente. La clave no lleva numero
 * de version porque la lista es de la novela entera, y se suelta con ella.
 */
export function useVersions(novel: string) {
  return useResource(cacheKey(novel, 0, "versions"), () =>
    settle(() => api.GET("/novels/{novel_id}/versions", { params: { path: { novel_id: novel } } })),
  );
}

/** La vigente de una lista de versiones. Pura. */
export function currentVersion(versions: readonly VersionInfo[]): number {
  return versions.find((v) => v.current)?.number ?? versions.at(-1)?.number ?? 1;
}
