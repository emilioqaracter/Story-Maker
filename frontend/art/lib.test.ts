import { describe, expect, it } from "vitest";

import ignore from "./.gitignore?raw";
import { apiKey, extensionFor, findImage, generateContentBody, interactionsBody, parseEnv, pending, redact } from "./lib";

/* Las partes puras del generador (srs-frontend-v2 RF-276, RNF-60): sin clave y sin red. */

const IMAGE = "a".repeat(100);

describe("clave de Google AI Studio (RNF-60)", () => {
  it("el entorno gana al fichero, y el fichero admite comentarios, comillas y export", () => {
    const file = "# clave\nexport GEMINI_API_KEY='de-fichero'\n";
    expect(apiKey({ GEMINI_API_KEY: "de-entorno" }, file)).toBe("de-entorno");
    expect(apiKey({}, file)).toBe("de-fichero");
    expect(apiKey({}, "GOOGLE_API_KEY=otra")).toBe("otra");
    expect(apiKey({}, null)).toBeUndefined();
    expect(apiKey({ GEMINI_API_KEY: "  " }, "")).toBeUndefined();
    expect(parseEnv("SIN_IGUAL\n=vacio\nA=\nB=1").get("B")).toBe("1");
  });

  it("la clave nunca sale en un texto que se muestra", () => {
    expect(redact("error con clave-secreta-dummy en la url clave-secreta-dummy", "clave-secreta-dummy")).toBe(
      "error con [CLAVE] en la url [CLAVE]",
    );
  });

  it("el fichero de la clave esta en el .gitignore de art/", () => {
    expect(ignore.split(/\r?\n/)).toContain(".env.local");
  });

  it("ningun cuerpo de peticion lleva la clave: va solo en la cabecera", () => {
    const bodies = JSON.stringify([interactionsBody("m", "p", "2:3"), generateContentBody("p", "2:3")]);
    expect(bodies).not.toMatch(/key/i);
  });
});

describe("respuesta del modelo (RF-276)", () => {
  it("encuentra la imagen en la forma de interacciones y en la de generateContent", () => {
    expect(findImage({ outputs: [{ type: "text" }, { type: "image", mime_type: "image/jpeg", data: IMAGE }] })).toEqual({
      mime: "image/jpeg",
      data: IMAGE,
    });
    expect(
      findImage({ candidates: [{ content: { parts: [{ text: "hola" }, { inlineData: { mimeType: "image/png", data: IMAGE } }] } }] }),
    ).toEqual({ mime: "image/png", data: IMAGE });
  });

  it("sin imagen devuelve null, y un tipo raro no tiene extension", () => {
    expect(findImage({ candidates: [{ content: { parts: [{ text: "no puedo" }] } }] })).toBeNull();
    expect(findImage({ data: IMAGE, mime_type: "text/plain" })).toBeNull();
    expect(extensionFor("image/jpeg")).toBe("jpg");
    expect(extensionFor("image/png")).toBe("png");
    expect(extensionFor("image/gif")).toBeNull();
  });
});

describe("que se genera", () => {
  const ids = ["a", "b", "c"];
  it("solo lo que falta, todo con force, y acotado con only", () => {
    expect(pending(ids, ["a.jpg", "catalog.json"], { force: false, only: [] })).toEqual(["b", "c"]);
    expect(pending(ids, ["a.jpg"], { force: true, only: [] })).toEqual(ids);
    expect(pending(ids, ["b.png"], { force: false, only: ["b", "c"] })).toEqual(["c"]);
  });
});
