// De disco a archivos, y de archivos al modelo.
//
// Esta es la unica parte del lector que toca disco. El parser de verdad vive
// en web/src/lector y es puro: aqui solo se abren archivos y se le pasan. Asi
// el servidor y el modo estatico no pueden discrepar, porque son el mismo
// codigo leyendo el mismo texto.

import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

import { leerNovela, resumenDeNovela } from '../../../web/src/lector/index.ts'
import type { Archivos, Novela, Resumen } from '../../../web/src/lector/tipos.ts'

/** Las carpetas de una novela que el tablero lee. No hay mas. */
const CARPETAS = ['capitulos', 'decisiones', 'continuidad']

/** Los archivos sueltos de la raiz de una novela. */
const SUELTOS = ['plan.md', 'novela.md', 'sesion.json']

/**
 * Todo se lee como UTF-8, explicitamente. Los archivos lo son; lo que esta en
 * cp1252 es la consola de Windows. Leer sin declarar la codificacion convierte
 * cada tilde en dos caracteres y se ve en pantalla.
 */
async function leerTexto(ruta: string): Promise<string | null> {
  try {
    return await readFile(ruta, 'utf8')
  } catch {
    return null
  }
}

async function listarDirectorio(ruta: string): Promise<string[]> {
  try {
    const entradas = await readdir(ruta, { withFileTypes: true })
    return entradas.filter((e) => e.isFile()).map((e) => e.name)
  } catch {
    return []
  }
}

export async function leerArchivosDeNovela(libros: string, slug: string): Promise<Archivos> {
  const base = path.join(libros, slug)
  const archivos: Archivos = {}

  for (const nombre of SUELTOS) {
    const contenido = await leerTexto(path.join(base, nombre))
    if (contenido !== null) archivos[nombre] = contenido
  }

  for (const carpeta of CARPETAS) {
    const dir = path.join(base, carpeta)
    for (const nombre of await listarDirectorio(dir)) {
      const contenido = await leerTexto(path.join(dir, nombre))
      // La ruta del modelo lleva siempre barras normales, en Windows tambien:
      // es una clave, no un camino del sistema de archivos.
      if (contenido !== null) archivos[`${carpeta}/${nombre}`] = contenido
    }
  }

  return archivos
}

export async function leerNovelaDeDisco(libros: string, slug: string): Promise<Novela> {
  return leerNovela(slug, await leerArchivosDeNovela(libros, slug))
}

/** Una carpeta de books/ es una novela si tiene plan.md. */
export async function listarSlugs(libros: string): Promise<string[]> {
  let entradas
  try {
    entradas = await readdir(libros, { withFileTypes: true })
  } catch {
    return []
  }
  const slugs: string[] = []
  for (const e of entradas) {
    if (!e.isDirectory()) continue
    if ((await leerTexto(path.join(libros, e.name, 'plan.md'))) !== null) slugs.push(e.name)
  }
  return slugs.sort()
}

export async function listarNovelas(libros: string): Promise<Resumen[]> {
  const slugs = await listarSlugs(libros)
  const novelas = await Promise.all(slugs.map((s) => leerNovelaDeDisco(libros, s)))
  return novelas.map(resumenDeNovela)
}

/**
 * El frontmatter de .claude/agents/*.md, que es donde vive de verdad que
 * modelo usa cada agente. La vista de la cuenta lo necesita para decir cual es
 * "el que juzga" sin escribirlo a mano.
 */
export async function leerAgentes(raizRepo: string): Promise<Record<string, string>> {
  const dir = path.join(raizRepo, '.claude', 'agents')
  const archivos: Record<string, string> = {}
  for (const nombre of await listarDirectorio(dir)) {
    if (!nombre.endsWith('.md')) continue
    const contenido = await leerTexto(path.join(dir, nombre))
    if (contenido !== null) archivos[nombre] = contenido
  }
  return archivos
}
