import { http, HttpResponse, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";

import type { paths } from "../api/schema";

/**
 * Dobles del backend tipados por el mismo esquema que el cliente (RNF-46).
 * Un doble que devuelve algo que el esquema no declara no compila, asi que
 * las pruebas no pueden pasar contra un backend que no existe.
 */

type Method = "get" | "post";
type WithMethod<M extends Method> = {
  [P in keyof paths]: paths[P][M] extends { responses: unknown } ? P : never;
}[keyof paths];

type OkBody<Op> = Op extends { responses: infer R }
  ? R extends { 200: { content: { "application/json": infer B } } }
    ? B
    : R extends { 202: { content: { "application/json": infer B } } }
      ? B
      : R extends { 201: { content: { "application/json": infer B } } }
        ? B
        : never
  : never;

type BodyOf<Op> = Op extends { requestBody?: { content: { "application/json": infer B } } } ? B : undefined;

export interface Call<Body = undefined> {
  params: Record<string, string>;
  url: URL;
  body: Body;
}

type Resolver<B, Body = undefined> = (call: Call<Body>) => B | Response;

/** `/novels/{novel_id}` del esquema a `/novels/:novel_id` de msw. */
function toMsw(path: string): string {
  return path.replace(/\{([^}]+)\}/g, ":$1");
}

function origin(): string {
  return globalThis.location.origin;
}

export function onGet<P extends WithMethod<"get">>(path: P, resolve: Resolver<OkBody<paths[P]["get"]>>) {
  return http.get(`${origin()}${toMsw(path)}`, ({ params, request }) => {
    const out = resolve({ params: params as Record<string, string>, url: new URL(request.url), body: undefined });
    return out instanceof Response ? out : HttpResponse.json(out as JsonBodyType);
  });
}

/**
 * Un POST tipado por su cuerpo y su respuesta. El codigo de exito lo dice el
 * resolvedor con `created`; por defecto, 200.
 */
export function onPost<P extends WithMethod<"post">>(
  path: P,
  resolve: Resolver<OkBody<paths[P]["post"]>, BodyOf<paths[P]["post"]>>,
  created = false,
) {
  return http.post(`${origin()}${toMsw(path)}`, async ({ params, request }) => {
    const text = await request.text();
    const body = (text ? JSON.parse(text) : undefined) as BodyOf<paths[P]["post"]>;
    const out = resolve({ params: params as Record<string, string>, url: new URL(request.url), body });
    return out instanceof Response ? out : HttpResponse.json(out as JsonBodyType, { status: created ? 201 : 200 });
  });
}

export function notFound(detail: string): Response {
  return HttpResponse.json({ detail }, { status: 404 });
}

export function networkError(): Response {
  return HttpResponse.error();
}

export const server = setupServer();

/** Metodo y ruta de cada peticion que llega a los dobles, para afirmar sobre ellas. */
export const requests: { method: string; path: string }[] = [];
server.events.on("request:start", ({ request }) => {
  requests.push({ method: request.method, path: new URL(request.url).pathname });
});
