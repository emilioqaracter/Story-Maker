// Analisis estatico de frontend/ (VER-02). Cada restriccion lleva su requisito:
// si una deja de tener sentido, se quita con el requisito, no sola.

import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

import { boundaries } from "./eslint.rules.js";

/** RF-163, RNF-40: ningun texto se interpreta como HTML ni como codigo. */
const SECURITY = [
  { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: "Texto como nodo de texto, nunca como HTML (RF-163)" },
  { selector: "AssignmentExpression[left.property.name=/^(innerHTML|outerHTML)$/]", message: "Texto como nodo de texto, nunca como HTML (RF-163)" },
  { selector: "CallExpression[callee.property.name='insertAdjacentHTML']", message: "Texto como nodo de texto, nunca como HTML (RF-163)" },
  { selector: "CallExpression[callee.object.name='document'][callee.property.name=/^write(ln)?$/]", message: "Texto como nodo de texto, nunca como HTML (RF-163)" },
  { selector: "CallExpression[callee.name='eval']", message: "Ningun texto se ejecuta (RNF-40)" },
  { selector: "NewExpression[callee.name='Function']", message: "Ningun texto se ejecuta (RNF-40)" },
];
/** RI-55: el acceso HTTP vive solo en commons/api/. */
const NETWORK = [
  { selector: "CallExpression[callee.name='fetch']", message: "HTTP solo a traves del cliente de commons/api/ (RI-55)" },
  { selector: "MemberExpression[property.name='fetch'][object.name=/^(window|globalThis|self)$/]", message: "HTTP solo a traves del cliente de commons/api/ (RI-55)" },
  { selector: "NewExpression[callee.name=/^(XMLHttpRequest|WebSocket|EventSource)$/]", message: "HTTP solo a traves del cliente de commons/api/ (RI-55)" },
  { selector: "MemberExpression[property.name='sendBeacon']", message: "HTTP solo a traves del cliente de commons/api/ (RI-55)" },
];
/** RD-29: el almacenamiento del navegador vive solo en commons/storage/. */
const STORAGE = [
  { selector: "Identifier[name=/^(localStorage|sessionStorage|indexedDB)$/]", message: "El navegador guarda solo lo de commons/storage/ (RD-29)" },
  { selector: "MemberExpression[property.name='cookie'][object.name='document']", message: "El navegador guarda solo lo de commons/storage/ (RD-29)" },
];
/** RI-56: ninguna direccion que no sea la del backend, que es el mismo origen. */
const URLS = [
  { selector: "Literal[value=/^(https?|wss?):\\/\\//]", message: "Sin direcciones externas: la unica red es el backend, en el mismo origen (RI-56)" },
  { selector: "TemplateElement[value.raw=/^(https?|wss?):\\/\\//]", message: "Sin direcciones externas: la unica red es el backend, en el mismo origen (RI-56)" },
];

const TS = ["**/*.{ts,tsx}"];

export default tseslint.config(
  { ignores: ["node_modules/**", "dist/**", "commons/api/schema.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: TS,
    plugins: { "react-hooks": reactHooks, local: { rules: { boundaries } } },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "local/boundaries": "error",
      // RNF-43: sin `any` ni supresiones.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/ban-ts-comment": ["error", { "ts-expect-error": true, "ts-ignore": true, "ts-nocheck": true, "ts-check": false }],
      "no-restricted-syntax": ["error", ...SECURITY, ...NETWORK, ...STORAGE, ...URLS],
    },
  },
  { files: ["commons/api/**/*.{ts,tsx}"], rules: { "no-restricted-syntax": ["error", ...SECURITY, ...STORAGE, ...URLS] } },
  { files: ["commons/storage/**/*.{ts,tsx}"], rules: { "no-restricted-syntax": ["error", ...SECURITY, ...NETWORK, ...URLS] } },
  // La direccion del backend local en desarrollo es la unica que se escribe, y solo aqui.
  { files: ["vite.config.ts"], rules: { "no-restricted-syntax": ["error", ...SECURITY, ...NETWORK, ...STORAGE] } },
  {
    files: ["**/*.{js,mjs}"],
    plugins: { local: { rules: { boundaries } } },
    languageOptions: { globals: { process: "readonly", console: "readonly" } },
    rules: { "local/boundaries": "error" },
  },
);
