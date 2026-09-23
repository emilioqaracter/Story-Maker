/**
 * Lo unico que el frontend guarda en el navegador (RD-29): identificadores de
 * novelas y entrevistas visitadas, posicion de lectura por novela y version, y
 * ultima version elegida. Nada de prosa, fichas, brief ni estado de la tirada.
 *
 * Todo lo leido se valida: el almacenamiento es del navegador, no nuestro, y
 * puede traer cualquier cosa. Si el navegador no deja guardar, no se guarda y
 * la aplicacion sigue: nada de esto lo necesita el backend (RNF-39).
 */

const PREFIX = "story-maker:";
const NOVELS = `${PREFIX}novels`;
const INTERVIEWS = `${PREFIX}interviews`;
const POSITION = `${PREFIX}position:`;
const VERSION = `${PREFIX}version:`;

/** Cuantos identificadores se recuerdan: los ultimos visitados. */
const KEEP = 20;

const ID = /^[a-z0-9][a-z0-9-]{0,63}$/;

export interface Position {
  chapter: number;
}

function store(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function readJson(key: string): unknown {
  const raw = store()?.getItem(key);
  if (raw == null) return undefined;
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return undefined;
  }
}

function write(key: string, value: unknown): void {
  try {
    store()?.setItem(key, JSON.stringify(value));
  } catch {
    // Cuota llena o almacenamiento bloqueado: se sigue sin recordar.
  }
}

function ids(key: string): string[] {
  const value = readJson(key);
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string" && ID.test(v)) : [];
}

function remember(key: string, id: string): void {
  if (!ID.test(id)) return;
  write(key, [id, ...ids(key).filter((v) => v !== id)].slice(0, KEEP));
}

function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 1;
}

export const visitedNovels = (): string[] => ids(NOVELS);
export const rememberNovel = (id: string): void => remember(NOVELS, id);
export const visitedInterviews = (): string[] => ids(INTERVIEWS);
export const rememberInterview = (id: string): void => remember(INTERVIEWS, id);

export function readingPosition(novel: string, version: number): Position | undefined {
  const value = readJson(`${POSITION}${novel}:${version}`);
  if (value && typeof value === "object" && positive((value as Position).chapter)) {
    return { chapter: (value as Position).chapter };
  }
  return undefined;
}

export function saveReadingPosition(novel: string, version: number, position: Position): void {
  if (ID.test(novel) && positive(version) && positive(position.chapter)) {
    write(`${POSITION}${novel}:${version}`, { chapter: position.chapter });
  }
}

export function lastVersion(novel: string): number | undefined {
  const value = readJson(`${VERSION}${novel}`);
  return positive(value) ? value : undefined;
}

export function saveLastVersion(novel: string, version: number): void {
  if (ID.test(novel) && positive(version)) write(`${VERSION}${novel}`, version);
}

/** Olvida todo lo de esta aplicacion. Lo usan las pruebas entre casos. */
export function forgetAll(): void {
  const s = store();
  if (!s) return;
  for (const key of Object.keys(s)) if (key.startsWith(PREFIX)) s.removeItem(key);
}

/** Las claves que esta aplicacion escribe, para comprobar RD-29. */
export function storedKeys(): string[] {
  const s = store();
  return s ? Object.keys(s).filter((k) => k.startsWith(PREFIX)) : [];
}
