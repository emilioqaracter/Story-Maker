import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { rememberNovel } from "../storage/local";
import { NOVEL, novelHandlers } from "../testing/fixtures";
import { renderAt } from "../testing/render";
import { networkError, onGet, server } from "../testing/server";
import { Home } from "./Home";

describe("portada de la aplicacion (RF-166)", () => {
  it("lista las novelas de RI-37 con su estado y sus versiones, y da acceso a encargar", async () => {
    server.use(...novelHandlers());
    renderAt([{ path: "/", element: <Home /> }], "/");
    const link = await screen.findByRole("link", { name: "El verano de Rex" });
    expect(link.getAttribute("href")).toBe(`/novels/${NOVEL}`);
    expect(screen.getByText(/1 versión · Obra cerrada/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Encargar una novela nueva/ }).getAttribute("href")).toBe("/new");
  });

  it("si RI-37 no responde, quedan las visitadas en este navegador y lo dice", async () => {
    rememberNovel("prueba-dos");
    server.use(onGet("/novels", () => networkError()));
    renderAt([{ path: "/", element: <Home /> }], "/");
    expect(await screen.findByText(/No se pudo leer la lista de novelas/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "prueba-dos" })).toBeTruthy();
  });
});
