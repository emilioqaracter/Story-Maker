// El estado de una novela que se esta escribiendo ahora.
//
// Casi todo sale de la carpeta, igual que en el replay: los capitulos, los
// intentos y las luces estan en disco en cuanto existen. Lo unico que la
// carpeta no puede contar es **quien esta trabajando en este segundo**, porque
// un agente despachado no deja rastro hasta que termina. Eso, y solo eso,
// viene del stream de Claude Code.

import type { Despachado } from '../datos/fuente.ts'
import type { Novela } from '../lector/tipos.ts'
import type { Casilla, Fila } from './guion.ts'

/** Los agentes encendidos ahora mismo, por nombre. */
export function trabajandoAhora(activos: Despachado[] | undefined): Set<string> {
  return new Set((activos ?? []).map((a) => a.agente))
}

/**
 * La rejilla de luces de una novela en curso.
 *
 * Las filas salen de `decisiones/`. Ademas, si hay un juez despachado sobre un
 * capitulo e intento que todavia no tiene archivo, se abre su fila en
 * "esperando": es verdad que ese juez esta leyendo, y verlo esperar es la
 * mitad de lo que cuenta la pantalla.
 */
export function filasEnVivo(novela: Novela | null, activos: Despachado[] = []): Fila[] {
  const filas = new Map<string, Fila>()

  for (const capitulo of novela?.capitulos ?? []) {
    for (const intento of capitulo.intentos) {
      const esUltimo = intento === capitulo.intentos[capitulo.intentos.length - 1]
      filas.set(`${capitulo.numero}.${intento.k}`, {
        capitulo: capitulo.numero,
        intento: intento.k,
        revisor: veredictoDe(intento.revisor),
        verificador: veredictoDe(intento.verificador),
        aprobado: esUltimo && capitulo.estado === 'aprobado',
      })
    }
  }

  for (const a of activos) {
    if (a.capitulo === null || a.intento === null) continue
    const clave = `${a.capitulo}.${a.intento}`
    const fila = filas.get(clave) ?? {
      capitulo: a.capitulo,
      intento: a.intento,
      revisor: 'pendiente' as Casilla,
      verificador: 'pendiente' as Casilla,
      aprobado: false,
    }
    if (a.agente === 'revisor' && fila.revisor === 'pendiente') fila.revisor = 'esperando'
    if (a.agente === 'verificador' && fila.verificador === 'pendiente') {
      fila.verificador = 'esperando'
    }
    filas.set(clave, fila)
  }

  return [...filas.values()].sort((a, b) => a.capitulo - b.capitulo || a.intento - b.intento)
}

function veredictoDe(luz: { veredicto: Casilla } | null): Casilla {
  return luz ? luz.veredicto : 'pendiente'
}

/** Lo que el tablero puede decir con honestidad que esta pasando. */
export function rotuloDe(activos: Despachado[] | undefined, rotulo: string | null): string {
  const lista = activos ?? []
  if (lista.length === 0) return rotulo ?? 'pensando'
  // Con los dos jueces a la vez, el rotulo los nombra juntos: no hay un orden
  // entre ellos y escribirlos en fila sugeriria que si lo hay.
  const jueces = lista.filter((a) => a.agente === 'revisor' || a.agente === 'verificador')
  if (jueces.length === 2) {
    const donde = jueces[0].descripcion.replace(/^\w+\s*·\s*/, '')
    return `revisor y verificador · ${donde}`
  }
  return lista.map((a) => a.descripcion).join('  ·  ')
}
