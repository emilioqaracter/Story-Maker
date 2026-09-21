// El guion del replay: la lista ordenada de lo que paso en una corrida.
//
// Los mtime no sirven. Git no guarda fechas de modificacion, asi que en
// cualquier maquina que haya clonado el repositorio los veintidos archivos de
// decisiones/ de adrian-2025 tienen la misma hora al segundo, la del checkout.
// El replay no reconstruye tiempos: reconstruye el orden, que si es
// determinista y sale de los nombres de archivo.

import type { Juez, Luz, Novela } from '../lector/tipos.ts'

export type Acontecimiento =
  | { tipo: 'plan'; ms: number }
  | { tipo: 'redactor'; ms: number; capitulo: number; intento: number }
  | { tipo: 'jueces'; ms: number; capitulo: number; intento: number }
  | { tipo: 'luces'; ms: number; capitulo: number; intento: number }
  | { tipo: 'motivo'; ms: number; capitulo: number; intento: number; juez: Juez }
  | { tipo: 'aprobado'; ms: number; capitulo: number }
  | { tipo: 'cierre'; ms: number }

/** Duraciones nominales, pensadas para que se lean en pantalla. */
export const DURACION = {
  plan: 2000,
  redactor: 3000,
  jueces: 2500,
  luces: 600,
  motivo: 4000,
  aprobado: 1200,
  cierre: 2500,
} as const

export function guionDe(novela: Novela): Acontecimiento[] {
  const guion: Acontecimiento[] = []
  if (novela.capitulosPrevistos.length > 0 || novela.capitulos.length > 0) {
    guion.push({ tipo: 'plan', ms: DURACION.plan })
  }

  for (const capitulo of novela.capitulos) {
    for (const intento of capitulo.intentos) {
      const c = capitulo.numero
      const k = intento.k
      guion.push({ tipo: 'redactor', ms: DURACION.redactor, capitulo: c, intento: k })
      guion.push({ tipo: 'jueces', ms: DURACION.jueces, capitulo: c, intento: k })
      guion.push({ tipo: 'luces', ms: DURACION.luces, capitulo: c, intento: k })

      // Cada roja abre su motivo. Es lo que separa este sistema de un filtro
      // automatico: el rechazo esta argumentado y se puede discutir.
      for (const juez of ['revisor', 'verificador'] as const) {
        if (intento[juez]?.veredicto === 'ROJA') {
          guion.push({ tipo: 'motivo', ms: DURACION.motivo, capitulo: c, intento: k, juez })
        }
      }
    }
    if (capitulo.estado === 'aprobado') {
      guion.push({ tipo: 'aprobado', ms: DURACION.aprobado, capitulo: capitulo.numero })
    }
  }

  if (novela.cierre !== null) guion.push({ tipo: 'cierre', ms: DURACION.cierre })
  return guion
}

export function duracionDe(guion: Acontecimiento[]): number {
  return guion.reduce((n, a) => n + a.ms, 0)
}

// --- el instante ---------------------------------------------------------
//
// Lo que se ve en pantalla en un punto del guion. Se calcula plegando los
// acontecimientos desde el principio: no hay estado escondido y moverse atras
// cuesta lo mismo que moverse adelante.

export type Casilla = 'pendiente' | 'esperando' | 'VERDE' | 'ROJA' | 'NO ENTENDIDA'

export type Fila = {
  capitulo: number
  intento: number
  revisor: Casilla
  verificador: Casilla
  aprobado: boolean
}

export type QuienTrabaja = 'arquitecto' | 'redactor' | 'jueces' | null

export type Instante = {
  quienTrabaja: QuienTrabaja
  capitulo: number | null
  intento: number | null
  filas: Fila[]
  /** La luz roja cuyo motivo esta abierto ahora mismo. */
  abierta: Luz | null
  aprobados: number
  /** Cuanto del guion se ha reproducido, de 0 a 1. */
  avance: number
  terminada: boolean
}

function casillaDe(luz: Luz | null | undefined): Casilla {
  if (!luz) return 'pendiente'
  return luz.veredicto
}

function luzDe(novela: Novela, capitulo: number, intento: number, juez: Juez): Luz | null {
  const c = novela.capitulos.find((x) => x.numero === capitulo)
  const i = c?.intentos.find((x) => x.k === intento)
  return i?.[juez] ?? null
}

export function instanteEn(novela: Novela, guion: Acontecimiento[], indice: number): Instante {
  const hasta = Math.max(-1, Math.min(indice, guion.length - 1))
  const filas = new Map<string, Fila>()
  const aprobadosVistos = new Set<number>()

  let quienTrabaja: QuienTrabaja = null
  let capitulo: number | null = null
  let intento: number | null = null
  let abierta: Luz | null = null
  let terminada = false

  for (let i = 0; i <= hasta; i++) {
    const a = guion[i]
    abierta = null

    switch (a.tipo) {
      case 'plan':
        quienTrabaja = 'arquitecto'
        break

      case 'redactor': {
        quienTrabaja = 'redactor'
        capitulo = a.capitulo
        intento = a.intento
        const clave = `${a.capitulo}.${a.intento}`
        if (!filas.has(clave)) {
          filas.set(clave, {
            capitulo: a.capitulo,
            intento: a.intento,
            revisor: 'pendiente',
            verificador: 'pendiente',
            aprobado: false,
          })
        }
        break
      }

      case 'jueces': {
        // Los dos a la vez. Si uno se encendiera antes que el otro, la
        // pantalla estaria contando una mentira sobre como funciona.
        quienTrabaja = 'jueces'
        capitulo = a.capitulo
        intento = a.intento
        const fila = filas.get(`${a.capitulo}.${a.intento}`)
        if (fila) {
          fila.revisor = 'esperando'
          fila.verificador = 'esperando'
        }
        break
      }

      case 'luces': {
        quienTrabaja = null
        capitulo = a.capitulo
        intento = a.intento
        const fila = filas.get(`${a.capitulo}.${a.intento}`)
        if (fila) {
          fila.revisor = casillaDe(luzDe(novela, a.capitulo, a.intento, 'revisor'))
          fila.verificador = casillaDe(luzDe(novela, a.capitulo, a.intento, 'verificador'))
        }
        break
      }

      case 'motivo':
        quienTrabaja = null
        capitulo = a.capitulo
        intento = a.intento
        abierta = luzDe(novela, a.capitulo, a.intento, a.juez)
        break

      case 'aprobado': {
        quienTrabaja = null
        aprobadosVistos.add(a.capitulo)
        const suyas = [...filas.values()].filter((f) => f.capitulo === a.capitulo)
        const ultima = suyas[suyas.length - 1]
        if (ultima) ultima.aprobado = true
        break
      }

      case 'cierre':
        quienTrabaja = null
        terminada = true
        break
    }
  }

  const total = guion.length
  return {
    quienTrabaja,
    capitulo,
    intento,
    filas: [...filas.values()],
    abierta,
    aprobados: aprobadosVistos.size,
    avance: total === 0 ? 0 : (hasta + 1) / total,
    terminada,
  }
}
