import { describe, expect, it } from "vitest";

import { NOVEL } from "../testing/fixtures";
import { networkError, onGet, server } from "../testing/server";
import { api } from "./client";
import { classify, settle } from "./errors";

describe("fallos de lectura (RF-164)", () => {
  it("un identificador que no existe, o con forma invalida, es «no existe»", () => {
    expect(classify(404, { detail: "no esta" })).toEqual({ kind: "not-found", detail: "no esta" });
    expect(classify(400, { detail: "forma" }).kind).toBe("not-found");
    expect(classify(500, { detail: "roto" })).toEqual({ kind: "server", status: 500, detail: "roto" });
  });

  it("sin respuesta es un fallo de red, no una excepcion", async () => {
    server.use(onGet("/novels/{novel_id}", () => networkError()));
    const outcome = await settle(() => api.GET("/novels/{novel_id}", { params: { path: { novel_id: NOVEL } } }));
    expect(outcome).toEqual({ ok: false, failure: { kind: "network" } });
  });
});
