import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NOVEL, novelHandlers, RequestsDouble } from "../../commons/testing/fixtures";
import { renderAt } from "../../commons/testing/render";
import { manuscriptRoutes } from "../routes";

describe("solicitudes de cambio (RF-189, RF-191)", () => {
  it("lista las solicitudes con su estado e interpretacion, sin ningun control sobre ellas", async () => {
    const double = new RequestsDouble();
    double.create({ text: "el perro se llama Nala", anchor: { kind: "fact", entity_id: "rex", attribute: "nombre" } });
    double.create({ text: "cámbialo", anchor: { kind: "fact", entity_id: "rex", attribute: "nombre" } });
    double.applyAll();
    const { server } = await import("../../commons/testing/server");
    server.use(...novelHandlers(undefined, double));
    const { container } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/changes`);
    expect(await screen.findByText(/versión 2 lista/)).toBeTruthy();
    expect(screen.getByText(/No se aplicará: La petición es ambigua/)).toBeTruthy();
    expect(container.querySelectorAll("button, form, input, textarea")).toHaveLength(0);
  });
});
