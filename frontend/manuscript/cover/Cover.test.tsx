import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { saveReadingPosition, visitedNovels } from "../../commons/storage/local";
import { NOVEL, novelHandlers, RequestsDouble, RUN_WRITING } from "../../commons/testing/fixtures";
import { renderAt } from "../../commons/testing/render";
import { networkError, onGet, requests, server } from "../../commons/testing/server";
import { manuscriptRoutes } from "../routes";

function twoVersions(): RequestsDouble {
  const r = new RequestsDouble();
  r.create({ text: "el perro se llama Nala", anchor: { kind: "fact", entity_id: "rex", attribute: "nombre" } });
  r.applyAll();
  return r;
}

describe("portada e indice (RF-177, RF-178, RF-182 a RF-184)", () => {
  it("muestra titulo, dedicatoria y destinatario de la version vigente, y su indice", async () => {
    server.use(...novelHandlers());
    renderAt(manuscriptRoutes, `/novels/${NOVEL}`);
    expect(await screen.findByRole("heading", { name: "El verano de Rex" })).toBeTruthy();
    expect(screen.getByText("Para Lucía, que nunca se rinde")).toBeTruthy();
    expect(screen.getByText("Una novela para Lucía")).toBeTruthy();
    expect(screen.getByText("Versión 1 · vigente")).toBeTruthy();
    const links = screen.getAllByRole("link", { name: /^Capítulo \d+$/ });
    expect(links.map((l) => l.getAttribute("href"))).toEqual([`/novels/${NOVEL}/v/1/chapters/1`, `/novels/${NOVEL}/v/1/chapters/2`]);
    expect(visitedNovels()).toEqual([NOVEL]);
  });

  it("con dos versiones, abre la vigente, marca lo cambiado y deja elegir la anterior", async () => {
    server.use(...novelHandlers(undefined, twoVersions()));
    renderAt(manuscriptRoutes, `/novels/${NOVEL}`);
    expect(await screen.findByText("Versión 2 · vigente")).toBeTruthy();
    expect(screen.getByText(/Cambió 1 capítulo respecto a la versión/)).toBeTruthy();
    expect(screen.getByText(/cambió en esta versión/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "1" }).getAttribute("href")).toBe(`/novels/${NOVEL}/v/1`);
  });

  it("la version anterior sigue legible y dice que no es la vigente", async () => {
    server.use(...novelHandlers(undefined, twoVersions()));
    renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1`);
    expect(await screen.findByText("Versión 1 · no es la vigente")).toBeTruthy();
    expect(screen.queryByText(/cambió en esta versión/)).toBeNull();
  });

  it("con la tirada en marcha, el capitulo en curso es una linea y no un capitulo; ningun borrador se pide", async () => {
    server.use(...novelHandlers(RUN_WRITING));
    renderAt(manuscriptRoutes, `/novels/${NOVEL}`);
    expect(await screen.findByText(/Escribiendo el capítulo 3, última escena cerrada: 1/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Capítulo 3" })).toBeNull();
    expect(requests.some((r) => r.path.endsWith("/chapters/3"))).toBe(false);
    expect(requests.every((r) => r.method === "GET")).toBe(true);
  });

  it("recuerda por donde iba el lector en esta version", async () => {
    server.use(...novelHandlers());
    saveReadingPosition(NOVEL, 1, { chapter: 2 });
    renderAt(manuscriptRoutes, `/novels/${NOVEL}`);
    const link = await screen.findByRole("link", { name: /Seguir leyendo: capítulo 2/ });
    expect(link.getAttribute("href")).toBe(`/novels/${NOVEL}/v/1/chapters/2`);
  });

  it("una novela que no existe es «no existe» (RF-164)", async () => {
    server.use(...novelHandlers());
    renderAt(manuscriptRoutes, "/novels/no-existe");
    expect(await screen.findByRole("heading", { name: "No existe" })).toBeTruthy();
  });

  it("una version que no existe tambien", async () => {
    server.use(...novelHandlers());
    renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/3`);
    expect(await screen.findByRole("heading", { name: "No existe" })).toBeTruthy();
  });

  it("sin red, lo dice y deja volver a cargar la lectura", async () => {
    server.use(onGet("/novels/{novel_id}", () => networkError()), ...novelHandlers());
    renderAt(manuscriptRoutes, `/novels/${NOVEL}`);
    const retry = await screen.findByRole("button", { name: "Volver a cargar" });
    server.use(...novelHandlers());
    fireEvent.click(retry);
    expect(await screen.findByRole("heading", { name: "El verano de Rex" })).toBeTruthy();
  });
});
