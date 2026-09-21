// El reloj del replay es un store con suscripcion y nada mas.
//
// El reloj real se ensena, pero no gobierna: en pantalla aparece lo que la
// novela tardo de verdad, de sesion.json, mientras la animacion corre a su
// propio ritmo. Confundir las dos cosas seria fingir un directo.

import { create } from 'zustand'

import type { ModeloDeAgente, Novela } from '../lector/index.ts'
import { guionDe } from './guion.ts'
import type { Acontecimiento } from './guion.ts'

export type Vista = 'circulo' | 'expediente' | 'cuenta'
export type Modo = 'replay' | 'vivo'

/**
 * Las dos pestanas.
 *
 * `historial` mira corridas que ya pasaron: se reproducen, se auditan y se
 * cuentan. `escribir` pide una novela nueva y la mira nacer. Son dos cosas
 * distintas —una lee y la otra provoca— y mezclarlas en la misma pantalla
 * hacia que no se encontrase ninguna de las dos.
 */
export type Pestana = 'historial' | 'escribir'

export const VELOCIDADES = [0.5, 1, 1.5, 2, 3, 4] as const

export type Tablero = {
  novela: Novela | null
  agentes: ModeloDeAgente[]
  guion: Acontecimiento[]
  indice: number
  corriendo: boolean
  velocidad: number
  vista: Vista
  pestana: Pestana
  modo: Modo
  modoGrabacion: boolean
  /** El capitulo que ensena la vista del expediente. */
  capituloAbierto: number | null
  /** La vista del expediente ensena la novela entera, no un capitulo. */
  verCierre: boolean
  /** El panel que ensena el archivo de decision tal como esta en disco. */
  verCrudo: boolean

  ponerNovela: (novela: Novela, modo: Modo) => void
  ponerAgentes: (agentes: ModeloDeAgente[]) => void
  reproducir: () => void
  pausar: () => void
  alternarReproduccion: () => void
  adelante: () => void
  atras: () => void
  cambiarVelocidad: (paso: number) => void
  irA: (vista: Vista) => void
  irAPestana: (pestana: Pestana) => void
  abrirCapitulo: (numero: number) => void
  abrirCierre: () => void
  alternarGrabacion: () => void
  alternarCrudo: () => void
}

export const usarTablero = create<Tablero>((set, get) => ({
  novela: null,
  agentes: [],
  guion: [],
  indice: 0,
  corriendo: false,
  velocidad: 1,
  vista: 'circulo',
  pestana: 'historial',
  modo: 'replay',
  modoGrabacion: false,
  capituloAbierto: null,
  verCierre: false,
  verCrudo: false,

  ponerNovela: (novela, modo) => {
    const guion = guionDe(novela)
    const anterior = get()
    const mismaNovela = anterior.novela?.slug === novela.slug

    // En vivo el tablero ensena siempre el final del guion: lo que hay en la
    // carpeta ahora. En replay se empieza por el principio, salvo que sea la
    // misma novela que ya se estaba mirando.
    const indice =
      modo === 'vivo'
        ? Math.max(0, guion.length - 1)
        : mismaNovela
          ? Math.min(anterior.indice, Math.max(0, guion.length - 1))
          : 0

    set({
      novela,
      guion,
      modo,
      indice,
      corriendo: modo === 'replay' ? anterior.corriendo && mismaNovela : false,
      capituloAbierto:
        mismaNovela && anterior.capituloAbierto !== null
          ? anterior.capituloAbierto
          : (novela.capitulos.find((c) => c.estado === 'aprobado')?.numero ??
            novela.capitulos[0]?.numero ??
            null),
    })
    latir()
  },

  ponerAgentes: (agentes) => set({ agentes }),

  reproducir: () => {
    const { guion, indice, modo } = get()
    if (modo !== 'replay' || guion.length === 0) return
    // Si estaba al final, volver a empezar.
    set({ corriendo: true, indice: indice >= guion.length - 1 ? 0 : indice })
    latir()
  },

  pausar: () => {
    set({ corriendo: false })
    limpiar()
  },

  alternarReproduccion: () => (get().corriendo ? get().pausar() : get().reproducir()),

  adelante: () => {
    const { indice, guion } = get()
    set({ indice: Math.min(indice + 1, Math.max(0, guion.length - 1)) })
    if (get().corriendo) latir()
  },

  atras: () => {
    set({ indice: Math.max(0, get().indice - 1) })
    if (get().corriendo) latir()
  },

  cambiarVelocidad: (paso) => {
    const actual = VELOCIDADES.indexOf(get().velocidad as (typeof VELOCIDADES)[number])
    const siguiente = Math.min(VELOCIDADES.length - 1, Math.max(0, actual + paso))
    set({ velocidad: VELOCIDADES[siguiente] })
    if (get().corriendo) latir()
  },

  irA: (vista) => set({ vista, pestana: 'historial' }),

  irAPestana: (pestana) => set({ pestana }),

  abrirCapitulo: (numero) => {
    const { novela } = get()
    if (!novela) return
    const hay = novela.capitulos.some((c) => c.numero === numero)
    if (hay) set({ capituloAbierto: numero, verCierre: false, verCrudo: false })
  },

  abrirCierre: () => {
    if (get().novela?.cierre) set({ verCierre: true, verCrudo: false })
  },

  alternarGrabacion: () => set({ modoGrabacion: !get().modoGrabacion }),

  alternarCrudo: () => set({ verCrudo: !get().verCrudo }),
}))

// --- el latido -----------------------------------------------------------

let temporizador: ReturnType<typeof setTimeout> | null = null

function limpiar() {
  if (temporizador !== null) {
    clearTimeout(temporizador)
    temporizador = null
  }
}

function latir() {
  limpiar()
  const { corriendo, guion, indice, velocidad, modo } = usarTablero.getState()
  if (!corriendo || modo !== 'replay' || guion.length === 0) return

  const ms = (guion[indice]?.ms ?? 800) / velocidad
  temporizador = setTimeout(() => {
    const t = usarTablero.getState()
    if (!t.corriendo) return
    if (t.indice >= t.guion.length - 1) {
      usarTablero.setState({ corriendo: false })
      return
    }
    usarTablero.setState({ indice: t.indice + 1 })
    latir()
  }, ms)
}
