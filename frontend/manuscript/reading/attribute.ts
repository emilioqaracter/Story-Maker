/**
 * A que escena pertenece una seleccion del lector (RF-180).
 *
 * Una seleccion se atribuye a exactamente una escena si sus dos extremos caen
 * en ella, y a ninguna si cruza dos: una peticion de cambio ancla en una escena
 * o no ancla (spec §7.3). Las dos funciones dicen lo mismo, una sobre
 * desplazamientos y otra sobre el DOM.
 */

/** Una escena como tramo del texto de lectura, `[start, end)`. */
export interface SceneSpan {
  id: string;
  start: number;
  end: number;
}

function containing(spans: readonly SceneSpan[], offset: number): SceneSpan | undefined {
  return spans.find((s) => s.start <= offset && offset < s.end);
}

/** Pura (RNF-47). `from` y `to` en cualquier orden; una seleccion vacia no se atribuye. */
export function attribute(spans: readonly SceneSpan[], from: number, to: number): string | null {
  if (from === to) return null;
  const a = containing(spans, Math.min(from, to));
  const b = containing(spans, Math.max(from, to) - 1);
  return a !== undefined && a === b ? a.id : null;
}

export const SCENE_ATTRIBUTE = "data-scene-id";

function sceneOf(node: Node | null): string | null {
  const element = node instanceof Element ? node : (node?.parentElement ?? null);
  return element?.closest(`[${SCENE_ATTRIBUTE}]`)?.getAttribute(SCENE_ATTRIBUTE) ?? null;
}

/** La misma regla sobre la seleccion del navegador. */
export function attributeSelection(selection: Selection | null): string | null {
  if (selection === null || selection.isCollapsed || selection.rangeCount === 0) return null;
  const a = sceneOf(selection.anchorNode);
  const b = sceneOf(selection.focusNode);
  return a !== null && a === b ? a : null;
}
