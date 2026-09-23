import { cache } from "./cache";
import { api, type Schemas } from "./client";
import { settle } from "./errors";
import { usePolled } from "./poll";

export type RunState = Schemas["RunState"];

/** Mientras la obra no este cerrada, el estado puede cambiar y se sigue sondeando. */
export function inProgress(state: RunState): boolean {
  return state.closed === null || state.closed === undefined;
}

/**
 * El estado de la tirada (RI-03), sondeado mientras la obra no este cerrada.
 *
 * Es tambien la senal de la cache (RD-28): cada estado que llega se contrasta
 * con el anterior, y un capitulo congelado mas suelta la cache de la novela.
 * Lo usan la portada del manuscrito y la vista de estado.
 */
export function useRunState(novel: string | undefined) {
  return usePolled(
    novel ?? null,
    async () => {
      const outcome = await settle(() =>
        api.GET("/novels/{novel_id}", { params: { path: { novel_id: novel ?? "" } } }),
      );
      if (outcome.ok && novel !== undefined) {
        cache.observe(novel, { frozenChapters: outcome.data.frozen_chapters, closed: outcome.data.closed ?? null });
      }
      return outcome;
    },
    inProgress,
  );
}

/** La linea de estado de la tirada, en palabras (RF-178, RF-182). Pura. */
export function describeRun(state: RunState): string {
  if (state.error) return `La tirada se detuvo con un error: ${state.error}`;
  if (state.closed === true) return `Obra cerrada con ${state.frozen_chapters} capítulos congelados.`;
  if (state.closed === false) {
    return `La tirada terminó sin cerrar la obra${state.reason ? `: ${state.reason}` : "."}`;
  }
  if (state.running && state.chapter_in_progress != null) {
    const scene = state.last_closed_scene != null ? `, última escena cerrada: ${state.last_closed_scene}` : "";
    return `Escribiendo el capítulo ${state.chapter_in_progress}${scene}.`;
  }
  if (state.running) return "La tirada está en marcha.";
  return `Sin tirada en marcha. ${state.frozen_chapters} capítulos congelados.`;
}
