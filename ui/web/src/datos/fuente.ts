// De donde salen los acontecimientos.
//
// El tablero hace lo mismo en los dos modos; lo unico que cambia es esto. En
// vivo los archivos llegan segun aparecen, por SSE desde el servidor. En
// replay salen de un volcado de books/ hecho de antemano. En los dos casos el
// modelo lo construye el mismo lector, asi que el tablero no sabe —ni le hace
// falta— de donde vino el texto.

import { leerModelosDeAgentes, leerNovela, resumenDeNovela } from '../lector/index.ts'
import type { Archivos, ModeloDeAgente, Novela, Resumen } from '../lector/index.ts'

/** Un subagente que esta corriendo ahora mismo, tal como lo cuenta el stream. */
export type Despachado = {
  id: string
  agente: string
  descripcion: string
  capitulo: number | null
  intento: number | null
  desde: number
}

export type EstadoCorrida = {
  slug: string
  idea: string
  empezada: number
  activos: Despachado[]
  rotulo: string | null
  terminada: boolean
  fallo: string | null
}

export type Carga = { novela: Novela | null; corrida: EstadoCorrida | null }

export type Volcado = {
  generado: string | null
  agentes: Record<string, string>
  novelas: Record<string, Archivos>
}

export type Salud = {
  claudeEnPath: boolean
  librosLegibles: boolean
  libros: string
  agentes: Record<string, string>
  corriendo: string | null
  corrida: EstadoCorrida | null
}

export type Fuente = {
  /** Si hay servidor detras, y por tanto se puede escribir una novela nueva. */
  hayServidor: boolean
  /** Lo que la etiqueta de pantalla tiene que decir de esta fuente. */
  origen: string
  listar: () => Promise<Resumen[]>
  abrir: (slug: string) => Promise<Novela>
  /** Se suscribe a una novela. Devuelve como darse de baja. */
  seguir: (slug: string, alCambiar: (carga: Carga) => void) => () => void
  /**
   * Se suscribe a la novela que se esta escribiendo ahora, sea cual sea.
   *
   * Hace falta una suscripcion aparte porque al lanzar todavia no hay slug: la
   * skill lo elige cuando ya ha empezado, y el servidor lo adopta al ver
   * aparecer la carpeta.
   */
  seguirLaQueSeEscribe: (alCambiar: (carga: Carga) => void) => () => void
  agentes: () => Promise<ModeloDeAgente[]>
  lanzar: ((idea: string) => Promise<EstadoCorrida>) | null
  parar: (() => Promise<void>) | null
  salud: () => Promise<Salud | null>
}

const LA_QUE_SE_ESCRIBE = '_corriendo'

// --- el servidor ---------------------------------------------------------

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const r = await fetch(ruta, opciones)
  if (!r.ok) {
    const cuerpo = (await r.json().catch(() => null)) as { error?: string } | null
    throw new Error(cuerpo?.error ?? `${ruta} respondio ${r.status}`)
  }
  return (await r.json()) as T
}

function suscribir(slug: string, alCambiar: (carga: Carga) => void): () => void {
  const flujo = new EventSource(`/api/novelas/${slug}/eventos`)
  flujo.onmessage = (e) => {
    try {
      alCambiar(JSON.parse(e.data) as Carga)
    } catch {
      // Un evento que no se entiende no puede tirar la pantalla.
    }
  }
  return () => flujo.close()
}

function fuenteDeServidor(salud: Salud): Fuente {
  return {
    hayServidor: true,
    origen: 'servidor',
    listar: () => pedir<Resumen[]>('/api/novelas'),
    abrir: (slug) => pedir<Novela>(`/api/novelas/${slug}`),
    seguir: suscribir,
    seguirLaQueSeEscribe: (alCambiar) => suscribir(LA_QUE_SE_ESCRIBE, alCambiar),
    agentes: async () => leerModelosDeAgentes(salud.agentes),
    lanzar: (idea) =>
      pedir<EstadoCorrida>('/api/novelas', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ idea }),
      }),
    parar: async () => {
      await pedir<{ parado: boolean }>('/api/novelas', { method: 'DELETE' })
    },
    salud: () => pedir<Salud>('/api/salud'),
  }
}

// --- el volcado ----------------------------------------------------------

function fuenteDeVolcado(volcado: Volcado): Fuente {
  const abrir = async (slug: string): Promise<Novela> => {
    const archivos = volcado.novelas[slug]
    if (!archivos) throw new Error(`el volcado no trae ${slug}`)
    return leerNovela(slug, archivos)
  }
  return {
    hayServidor: false,
    origen: volcado.generado ? `volcado del ${volcado.generado}` : 'volcado',
    listar: async () =>
      Object.entries(volcado.novelas)
        .map(([slug, archivos]) => resumenDeNovela(leerNovela(slug, archivos)))
        .sort((a, b) => a.slug.localeCompare(b.slug)),
    abrir,
    // Un volcado no cambia. Darse de baja no tiene nada que deshacer.
    seguir: () => () => {},
    seguirLaQueSeEscribe: () => () => {},
    agentes: async () => leerModelosDeAgentes(volcado.agentes),
    lanzar: null,
    parar: null,
    salud: async () => null,
  }
}

// --- cual de las dos -----------------------------------------------------

async function cargarVolcado(): Promise<Volcado | null> {
  try {
    const modulo = (await import('./volcado.json')) as { default: Volcado }
    const v = modulo.default
    return v && Object.keys(v.novelas ?? {}).length > 0 ? v : null
  } catch {
    return null
  }
}

/**
 * Primero el servidor; si no contesta, el volcado.
 *
 * Es el orden que hace falta el dia de la grabacion: si algo del servidor
 * falla, el tablero sigue reproduciendo corridas reales sin tocar una linea.
 */
export async function elegirFuente(): Promise<Fuente> {
  try {
    // Abierto con doble clic no hay servidor al que preguntar, y preguntarlo
    // igual solo deja un error rojo en la consola el dia de la grabacion.
    if (location.protocol === 'file:') throw new Error('sin servidor')
    const salud = await pedir<Salud>('/api/salud')
    return fuenteDeServidor(salud)
  } catch {
    const volcado = await cargarVolcado()
    if (volcado) return fuenteDeVolcado(volcado)
    throw new Error(
      'No hay servidor ni volcado. Arranca el servidor con "npm run dev" o genera el volcado con "npm run volcar".',
    )
  }
}
