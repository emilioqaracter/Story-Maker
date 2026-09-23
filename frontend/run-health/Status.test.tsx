import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POLL_MS } from "../commons/api/poll";
import { HOSTILE, NOVEL, novelHandlers, RUN_CLOSED, RUN_WRITING } from "../commons/testing/fixtures";
import { onGet, requests, server } from "../commons/testing/server";
import { Status } from "./Status";

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
