import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderAt } from "../testing/render";
import { Layout } from "./Layout";

const routes = [{ path: "/", element: <Layout />, children: [{ path: "novels/:id", element: <p>lectura</p> }, { index: true, element: <p>inicio</p> }] }];

describe("el armazon con la marca (BRAND.md §2)", () => {
  it("la cabecera muestra el logo una sola vez, con texto alternativo, y el nombre lleva al inicio", () => {
    renderAt(routes, "/");
    const banner = screen.getByRole("banner");
    const logos = within(banner).getAllByRole("img");
    expect(logos).toHaveLength(1);
    expect(logos[0]?.getAttribute("alt")).toBeTruthy();
    expect(logos[0]?.getAttribute("src")).toMatch(/logo-negativo/);
    // No se recorta ni se estira: solo se fija el alto y el ancho sale de la proporcion del archivo.
    expect((logos[0] as HTMLImageElement).style.width).toBe("auto");
    expect(within(banner).getByRole("link", { name: "Story Maker" }).getAttribute("href")).toBe("/");
    // Fuera de la cabecera, ni en el contenido: la marca se queda en el marco.
    expect(within(screen.getByRole("main")).queryAllByRole("img")).toHaveLength(0);
  });

  it("un enlace de salto lleva al contenido, que puede recibir el foco", () => {
    renderAt(routes, "/");
    const skip = screen.getByRole("link", { name: "Saltar al contenido" });
    expect(skip.getAttribute("href")).toBe("#contenido");
    const main = screen.getByRole("main");
    expect(main.id).toBe("contenido");
    expect(main.getAttribute("tabindex")).toBe("-1");
  });

  it("dentro de una novela, la navegacion marca donde estas y no tiene ningun control del ciclo", () => {
    renderAt(routes, "/novels/prueba-uno");
    const nav = screen.getByRole("navigation", { name: "Novela" });
    expect(within(nav).getByRole("link", { name: "Lectura" }).getAttribute("aria-current")).toBe("page");
    expect(within(nav).getAllByRole("link")).toHaveLength(4);
    expect(screen.getByRole("banner").querySelectorAll("button, form, input, select, textarea")).toHaveLength(0);
  });
});
