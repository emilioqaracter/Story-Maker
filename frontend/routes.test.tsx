import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NOVEL, novelHandlers, RUN_WRITING } from "./commons/testing/fixtures";
import { renderAt } from "./commons/testing/render";
import { server } from "./commons/testing/server";
import { addresses, routes } from "./routes";

describe("direcciones de la aplicacion (RF-165, RNF-42)", () => {
  it("son las diez de la spec y ninguna mas", () => {
    expect(addresses().sort()).toEqual(
      [
        "/",
        "/new",
        "/interviews/:iid",
        "/novels/:id",
        "/novels/:id/v/:v",
        "/novels/:id/v/:v/chapters/:n",
        "/novels/:id/bible",
        "/novels/:id/bible/:eid",
        "/novels/:id/changes",
        "/novels/:id/status",
      ].sort(),
    );
  });

  it("no llevan mas que identificadores: ni brief ni prosa viajan en la URL", () => {
    for (const address of addresses()) {
      const params = address.split("/").filter((s) => s.startsWith(":"));
      expect(params.every((p) => [":id", ":v", ":n", ":iid", ":eid"].includes(p))).toBe(true);
    }
  });

  it("una direccion desconocida dice «no existe»", () => {
    renderAt(routes, "/novels/prueba-uno/algo-que-no-existe");
    expect(screen.getByRole("heading", { name: "No existe" })).toBeTruthy();
  });

  it("la ficha y las solicitudes se montan en sus direcciones", async () => {
    server.use(...novelHandlers());
    renderAt(routes, `/novels/${NOVEL}/bible`);
    expect(await screen.findByRole("heading", { name: "Personajes y lugares" })).toBeTruthy();
  });
});

describe("la pagina de estado (RF-196 a RF-199)", () => {
  it("junta estado, deuda y grafo, y no tiene ningun control", async () => {
    server.use(...novelHandlers(RUN_WRITING));
    const { container } = renderAt(routes, `/novels/${NOVEL}/status`);
    await screen.findByText(/Escribiendo el capítulo 3/);
    await screen.findByText("La lesión de rodilla de Marcos");
    await screen.findByRole("img", { name: "Grafo de entidades" });
    await screen.findByText(/note=/);
    const main = container.querySelector("main");
    expect(main?.querySelectorAll("button, form, input, select, textarea")).toHaveLength(0);
  });
});
