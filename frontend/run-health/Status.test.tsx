import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POLL_MS } from "../commons/api/poll";
import { HOSTILE, NOVEL, novelHandlers, RUN_CLOSED, RUN_WRITING } from "../commons/testing/fixtures";
import { onGet, requests, server } from "../commons/testing/server";
import { formatCost, formatDuration, Status } from "./Status";

afterEach(() => {
  vi.useRealTimers();
});

const stateCalls = () => requests.filter((r) => r.path === `/novels/${NOVEL}`).length;

describe("estado de la tirada y traza (RF-198, RF-199)", () => {
  it("muestra el estado de RI-03 y los ultimos registros de RI-27, en lectura", async () => {
    server.use(...novelHandlers());
    render(<Status novel={NOVEL} />);
    expect(await screen.findByText(/Obra cerrada con 2 capítulos congelados/)).toBeTruthy();
    expect(screen.getByText("Cuarentenas").nextElementSibling?.textContent).toBe("1");
    expect(screen.getByText("Tiempo de redacción").nextElementSibling?.textContent).toBe("11 min 14 s");
    expect(screen.getByText("Coste").nextElementSibling?.textContent).toBe(formatCost(1.749587));
    const table = await screen.findByRole("table");
    expect(within(table).getByText(/note=/).textContent).toContain(HOSTILE);
    expect(document.querySelectorAll("button, form, input")).toHaveLength(0);
  });

  it("mientras la obra no este cerrada, vuelve a consultar a intervalo fijo, y al cerrarse para (D-59)", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    let state = RUN_WRITING;
    server.use(onGet("/novels/{novel_id}", () => state), ...novelHandlers());
    render(<Status novel={NOVEL} />);
    await vi.waitFor(() => expect(screen.getByText(/Escribiendo el capítulo 3/)).toBeTruthy());
    const before = stateCalls();
    state = RUN_CLOSED;
    await vi.advanceTimersByTimeAsync(POLL_MS);
    await vi.waitFor(() => expect(screen.getByText(/Obra cerrada/)).toBeTruthy());
    expect(stateCalls()).toBeGreaterThan(before);
    const after = stateCalls();
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    expect(stateCalls()).toBe(after);
  });
});

describe("tiempo de redaccion y coste (RF-285)", () => {
  it("formatea el tiempo en horas, minutos y segundos", () => {
    expect(formatDuration(0)).toBe("0 s");
    expect(formatDuration(42_400)).toBe("42 s");
    expect(formatDuration(673_720)).toBe("11 min 14 s");
    expect(formatDuration(3_900_000)).toBe("1 h 5 min");
  });

  it("formatea el coste en dolares, con dos decimales, y sin coste declarado una raya", () => {
    expect(formatCost(null)).toBe("—");
    expect(formatCost(1.749587)).toMatch(/1,75/);
    expect(formatCost(1.749587)).toMatch(/US\$|\$/);
  });
});
