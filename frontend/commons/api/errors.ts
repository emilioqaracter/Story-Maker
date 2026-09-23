/**
 * Como se lee un fallo de la API (RF-164, que refleja RI-10).
 *
 * - `not-found`: el backend dice que no existe. Un identificador con forma
 *   invalida (400) tampoco existe, y se trata igual.
 * - `network`: no hubo respuesta. Se ofrece repetir la lectura, que es un `GET`
 *   y no toca el ciclo: no es «reintentar la tirada», que no existe (RF-199).
 * - `server`: el backend respondio con un error que no es ninguno de los dos.
 */
export type Failure =
  | { kind: "not-found"; detail: string }
  | { kind: "network" }
  | { kind: "server"; status: number; detail: string };

export type Outcome<T> = { ok: true; data: T } | { ok: false; failure: Failure };

interface Answer<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * El motivo que da el backend. Un 422 de validacion trae una lista de errores,
 * cada uno con su `msg`: se unen, porque son la lista de lo que falla (RI-41).
 */
export function detailOf(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
        .filter(Boolean)
        .join(" · ");
    }
  }
  return "";
}

/** Clasifica un fallo por su estado HTTP. Pura. */
export function classify(status: number, error: unknown): Failure {
  if (status === 404 || status === 400 || status === 422) {
    return { kind: "not-found", detail: detailOf(error) };
  }
  return { kind: "server", status, detail: detailOf(error) };
}

/** Ejecuta una llamada del cliente y la convierte en un resultado sin excepciones. */
export async function settle<T>(call: () => Promise<Answer<T>>): Promise<Outcome<T>> {
  let answer: Answer<T>;
  try {
    answer = await call();
  } catch {
    return { ok: false, failure: { kind: "network" } };
  }
  if (answer.response.ok && answer.data !== undefined) return { ok: true, data: answer.data };
  return { ok: false, failure: classify(answer.response.status, answer.error) };
}
