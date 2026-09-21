// El servidor. Fino a proposito: seis rutas.
//
// books/ y .claude/ no se tocan. El tablero no escribe un solo byte dentro de
// ninguna de las dos, en ningun modo. Lo unico que este servidor puede
// provocar es que Claude Code escriba, igual que lo provoca la terminal.

import Fastify from 'fastify'
import { realpathSync } from 'node:fs'
import { access, constants } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  adoptarSlug,
  alCambiarCorrida,
  estadoDeCorrida,
  lanzar,
  loQueCorre,
  parar,
  rutaDeClaude,
  type EstadoCorrida,
} from './lanzador/index.ts'
import { leerAgentes, leerNovelaDeDisco, listarNovelas, listarSlugs } from './lector/index.ts'
import { vigilar } from './vigia/index.ts'
import type { Novela } from '../../web/src/lector/tipos.ts'

const PUERTO = Number(process.env.PUERTO ?? 4317)

const aqui = path.dirname(fileURLToPath(import.meta.url))
const raizRepo = path.resolve(aqui, '..', '..', '..')
// LIBROS permite apuntar a otra carpeta de novelas. Sirve para probar el vigia
// sin escribir en books/, que es lo que el tablero tiene prohibido.
const librosPedidos = process.env.LIBROS
  ? path.resolve(process.env.LIBROS)
  : path.join(raizRepo, 'books')

/**
 * La ruta se normaliza a su forma larga antes de vigilarla.
 *
 * En Windows, si aqui entra una ruta en formato corto 8.3 (EMILIO~1.ECH), los
 * eventos del sistema de archivos llegan con el nombre largo, libuv compara
 * las dos, falla una asercion y **mata el proceso entero**: no es una
 * excepcion que se pueda capturar. Pasa con cualquier carpeta bajo un perfil
 * de usuario con un punto en el nombre, que es justo el caso de esta maquina.
 */
function rutaLarga(ruta: string): string {
  try {
    return realpathSync.native(ruta)
  } catch {
    return ruta
  }
}

const libros = rutaLarga(librosPedidos)

const app = Fastify({ logger: false })

// --- los suscriptores del SSE -------------------------------------------
//
// Un conjunto de respuestas abiertas por novela. El servidor no guarda estado
// propio: esto no es el modelo, es la lista de quien esta mirando.
//
// Y una lista aparte, LA_QUE_SE_ESCRIBE, para quien mira la pestana de
// escribir: ahi todavia no hay slug al que suscribirse, porque el slug lo
// elige la skill cuando ya ha empezado.

const LA_QUE_SE_ESCRIBE = '_corriendo'

type Carga = { novela: Novela | null; corrida: EstadoCorrida | null }
type Suscriptor = { escribir: (dato: string) => void }

const suscriptores = new Map<string, Set<Suscriptor>>()

function apuntar(clave: string, s: Suscriptor) {
  if (!suscriptores.has(clave)) suscriptores.set(clave, new Set())
  suscriptores.get(clave)!.add(s)
}

function mandar(clave: string, carga: Carga) {
  const conjunto = suscriptores.get(clave)
  if (!conjunto || conjunto.size === 0) return
  const dato = `data: ${JSON.stringify(carga)}\n\n`
  for (const s of conjunto) s.escribir(dato)
}

async function leerSiExiste(slug: string): Promise<Novela | null> {
  if (!slug) return null
  try {
    return await leerNovelaDeDisco(libros, slug)
  } catch {
    return null
  }
}

/** La carga que ve quien mira una novela concreta. */
async function cargaDe(slug: string): Promise<Carga> {
  const corrida = estadoDeCorrida()
  return {
    novela: await leerSiExiste(slug),
    corrida: corrida && corrida.slug === slug ? corrida : null,
  }
}

/** La carga que ve quien mira la pestana de escribir. */
async function cargaDeLaQueSeEscribe(): Promise<Carga> {
  const corrida = estadoDeCorrida()
  return { novela: corrida ? await leerSiExiste(corrida.slug) : null, corrida }
}

let slugsConocidos = new Set<string>()

async function alCambiarArchivos(slug: string) {
  // Una novela que no existia mientras hay una corrida en marcha es esa
  // corrida: la skill elige el slug, no el tablero.
  if (!slugsConocidos.has(slug)) {
    slugsConocidos = new Set(await listarSlugs(libros))
    if (loQueCorre()) adoptarSlug(slug)
  }
  mandar(slug, await cargaDe(slug))
  if (estadoDeCorrida()?.slug === slug) mandar(LA_QUE_SE_ESCRIBE, await cargaDeLaQueSeEscribe())
}

// Cuando se enciende o se apaga un agente, el cambio no esta en ningun archivo
// y hay que mandarlo igual: es lo unico que la carpeta no puede contar.
alCambiarCorrida(() => {
  void (async () => {
    const carga = await cargaDeLaQueSeEscribe()
    mandar(LA_QUE_SE_ESCRIBE, carga)
    const slug = carga.corrida?.slug
    if (slug) mandar(slug, carga)
  })()
})

// --- las rutas -----------------------------------------------------------

app.get('/api/novelas', async () => listarNovelas(libros))

app.get<{ Params: { slug: string } }>('/api/novelas/:slug', async (peticion, respuesta) => {
  const { slug } = peticion.params
  if (!/^[a-z0-9._-]+$/i.test(slug)) return respuesta.code(400).send({ error: 'slug raro' })
  const novela = await leerNovelaDeDisco(libros, slug)
  if (novela.capitulosPrevistos.length === 0 && novela.capitulos.length === 0) {
    return respuesta.code(404).send({ error: `no hay nada en books/${slug}` })
  }
  return novela
})

app.get<{ Params: { slug: string } }>(
  '/api/novelas/:slug/eventos',
  async (peticion, respuesta) => {
    const { slug } = peticion.params
    const bruto = respuesta.raw

    bruto.writeHead(200, {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-cache, no-transform',
      connection: 'keep-alive',
      'x-accel-buffering': 'no',
    })

    const suscriptor: Suscriptor = {
      escribir: (dato) => {
        if (!bruto.writableEnded) bruto.write(dato)
      },
    }
    apuntar(slug, suscriptor)

    // El primer evento es el estado actual, para que quien se conecte a media
    // novela no tenga que esperar a que algo cambie.
    const carga =
      slug === LA_QUE_SE_ESCRIBE ? await cargaDeLaQueSeEscribe() : await cargaDe(slug)
    suscriptor.escribir(`data: ${JSON.stringify(carga)}\n\n`)

    const latido = setInterval(() => suscriptor.escribir(': latido\n\n'), 25_000)

    peticion.raw.on('close', () => {
      clearInterval(latido)
      suscriptores.get(slug)?.delete(suscriptor)
    })
  },
)

app.post<{ Body: { idea?: string } }>('/api/novelas', async (peticion, respuesta) => {
  const { idea } = peticion.body ?? {}
  if (typeof idea !== 'string' || idea.trim() === '') {
    return respuesta.code(400).send({ error: 'hace falta una idea' })
  }
  try {
    slugsConocidos = new Set(await listarSlugs(libros))
    // La idea va tal cual. La longitud, si la hay, viaja dentro de ella: es
    // una instruccion para el arquitecto, no un parametro del tablero.
    return lanzar(raizRepo, idea.trim())
  } catch (e: unknown) {
    return respuesta.code(409).send({ error: e instanceof Error ? e.message : String(e) })
  }
})

// Parar lo que se lanzo desde aqui. No es un paso del ciclo: es cerrar el
// proceso que abrimos, que es lo minimo que se le debe a quien le dio al boton.
app.delete('/api/novelas', async () => {
  parar()
  return { parado: true }
})

app.get('/api/salud', async () => {
  let librosLegibles = true
  try {
    await access(libros, constants.R_OK)
  } catch {
    librosLegibles = false
  }
  return {
    claudeEnPath: rutaDeClaude() !== null,
    librosLegibles,
    libros,
    agentes: await leerAgentes(raizRepo),
    corriendo: loQueCorre()?.slug ?? null,
    corrida: estadoDeCorrida(),
  }
})

// --- arranque ------------------------------------------------------------

slugsConocidos = new Set(await listarSlugs(libros))
const dejarDeVigilar = vigilar(libros, (slug) => void alCambiarArchivos(slug))

for (const senal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(senal, () => {
    parar()
    void dejarDeVigilar()
      .then(() => app.close())
      .then(() => process.exit(0))
  })
}

await app.listen({ port: PUERTO, host: '127.0.0.1' })

const claude = rutaDeClaude()
console.log(`tablero · servidor en http://127.0.0.1:${PUERTO}`)
console.log(`books/   ${libros}`)
console.log(`novelas  ${slugsConocidos.size}`)
console.log(`claude   ${claude ?? 'NO ENCONTRADO (no se va a poder escribir una novela nueva)'}`)
