/**
 * Marcas de cambio entre dos versiones (RF-184 a RF-186). Puras (RNF-47).
 *
 * El frontend no recalcula que cambio: lo dice el backend en el manifiesto y en
 * cada escena. Esto solo lo resume para la pantalla, y comprueba la promesa del
 * contrato: una escena sin marca tiene el mismo texto que en la version anterior.
 */

export interface MarkedChapter {
  number: number;
  changed: boolean;
}

export interface MarkedScene {
  scene_id: string;
  text: string;
  changed: boolean;
}

export function changedChapters(chapters: readonly MarkedChapter[]): number[] {
  return chapters.filter((c) => c.changed).map((c) => c.number);
}

/** Las escenas sin marca cuyo texto difiere del de la version anterior. Vacio si el contrato se cumple. */
export function broken(previous: readonly MarkedScene[], current: readonly MarkedScene[]): string[] {
  const before = new Map(previous.map((s) => [s.scene_id, s.text]));
  return current.filter((s) => !s.changed && before.has(s.scene_id) && before.get(s.scene_id) !== s.text).map((s) => s.scene_id);
}
