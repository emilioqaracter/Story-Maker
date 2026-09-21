// Vuelca books/ a un JSON que el front importa.
//
// Para grabar no hace falta servidor. Esto deja el texto de todas las novelas
// en un archivo, y `npm run build` lo mete dentro del index.html: una carpeta
// que se abre con doble clic y reproduce cualquier corrida.
//
// Es el modo que se usa si el dia de la grabacion algo falla, y el que
// permitiria enviar el tablero por un enlace sin tocar una linea.
//
//   npm run volcar

import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { leerAgentes, leerArchivosDeNovela, listarSlugs } from '../servidor/src/lector/index.ts'

const aqui = path.dirname(fileURLToPath(import.meta.url))
const raizRepo = path.resolve(aqui, '..', '..')
const libros = path.join(raizRepo, 'books')
const destino = path.join(aqui, '..', 'web', 'src', 'datos', 'volcado.json')

const slugs = await listarSlugs(libros)
const novelas: Record<string, Record<string, string>> = {}
for (const slug of slugs) {
  novelas[slug] = await leerArchivosDeNovela(libros, slug)
}

// El volcado lleva el texto tal cual, no el modelo ya construido: asi el
// parser del cliente es el mismo que corre en el servidor y no puede haber dos
// lecturas distintas del mismo archivo.
const volcado = {
  generado: new Date().toISOString().slice(0, 10),
  agentes: await leerAgentes(raizRepo),
  novelas,
}

await mkdir(path.dirname(destino), { recursive: true })
await writeFile(destino, JSON.stringify(volcado), 'utf8')

const bytes = Buffer.byteLength(JSON.stringify(volcado), 'utf8')
const archivos = Object.values(novelas).reduce((n, a) => n + Object.keys(a).length, 0)
console.log(`volcado: ${slugs.length} novelas, ${archivos} archivos, ${(bytes / 1024 / 1024).toFixed(2)} MB`)
console.log(path.relative(raizRepo, destino))
