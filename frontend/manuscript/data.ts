import { cacheKey } from "../commons/api/cache";
import { api, type Schemas } from "../commons/api/client";
import { settle } from "../commons/api/errors";
import { useResource } from "../commons/api/resource";

export type Manifest = Schemas["Manifest"];
export type ChapterEntry = Schemas["ChapterEntry"];
export type SceneAt = Schemas["SceneAt"];

/** `v` de la direccion a numero de version, o `null` si no tiene forma de version. */
export function parseVersion(param: string | undefined): number | null {
  return param !== undefined && /^\d+$/.test(param) && Number(param) >= 1 ? Number(param) : null;
}

/** RI-43. Una version publicada es inmutable: su cache no caduca (RD-28). */
export function useManifest(novel: string, version: number | null) {
  return useResource(version === null ? null : cacheKey(novel, version, "manifest"), () =>
    settle(() =>
      api.GET("/novels/{novel_id}/versions/{version}", {
        params: { path: { novel_id: novel, version: version ?? 1 } },
      }),
    ),
  );
}

/** RI-44. Las escenas del capitulo tal como estaban en esa version, con su identificador. */
export function useChapterAt(novel: string, version: number, chapter: number) {
  return useResource(cacheKey(novel, version, `chapter:${chapter}`), () =>
    settle(() =>
      api.GET("/novels/{novel_id}/versions/{version}/chapters/{number}", {
        params: { path: { novel_id: novel, version, number: chapter } },
      }),
    ),
  );
}
