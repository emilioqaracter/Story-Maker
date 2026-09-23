import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { cache } from "../api/cache";
import { forgetAll } from "../storage/local";
import { requests, server } from "./server";

// Una peticion que ningun doble contesta es un fallo, no una red real (RNF-46, RI-56).
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  cache.clear();
  forgetAll();
  requests.length = 0;
});
afterAll(() => server.close());
