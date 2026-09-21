// De sesion.json sale la cuenta. De ningun otro sitio.
//
// Aqui no se estima nada y no se llama a ninguna API. Si el archivo no esta,
// esta vacio o no se entiende, la cuenta es null y la pantalla dice "sin
// medir". Un numero inventado en esta vista se lleva por delante la
// credibilidad de las otras dos.

import type { Cuenta, Despacho, UsoModelo } from './tipos.ts'

function numero(v: unknown): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : 0
}

export function leerCuenta(crudo: string | undefined): Cuenta | null {
  if (!crudo || crudo.trim() === '') return null

  let j: Record<string, unknown>
  try {
    j = JSON.parse(crudo) as Record<string, unknown>
  } catch {
    return null
  }
  if (!j || typeof j !== 'object') return null

  // Sin coste total no hay cuenta. Sumar los modelos a mano para rellenarlo
  // seria construir el numero que la pantalla presenta como medido.
  if (typeof j.total_cost_usd !== 'number') return null

  const uso = (j.modelUsage ?? {}) as Record<string, Record<string, unknown>>
  const modelos: UsoModelo[] = Object.entries(uso)
    .map(([clave, m]) => ({
      modelo: typeof m.canonicalModel === 'string' ? m.canonicalModel : clave,
      costeUSD: numero(m.costUSD),
      entrada: numero(m.inputTokens) + numero(m.cacheReadInputTokens) + numero(m.cacheCreationInputTokens),
      salida: numero(m.outputTokens),
      razonamiento: numero(m.thinkingTokens),
    }))
    .sort((a, b) => b.costeUSD - a.costeUSD)

  const stats = (j.subagent_stats ?? {}) as Record<string, unknown>
  const porTipo = (stats.by_type ?? {}) as Record<string, unknown>
  const despachos: Despacho[] = Object.entries(porTipo)
    .map(([tipo, n]) => ({ tipo, n: numero(n) }))
    .sort((a, b) => b.n - a.n || a.tipo.localeCompare(b.tipo))

  const matados = (stats.killed ?? {}) as Record<string, unknown>
  const fallos =
    numero(stats.failed) + numero(matados.parent) + numero(matados.user) + numero(matados.system)

  // duration_ms es lo que tardo el ultimo turno; la corrida entera es
  // duration_api_ms. Para control-01 son 14 segundos contra 29 minutos, y lo
  // que la pantalla promete es lo segundo.
  const duracionMs = numero(j.duration_api_ms) || numero(j.duration_ms)

  return {
    costeUSD: j.total_cost_usd,
    duracionMs,
    modelos,
    despachos,
    subagentes: numero(stats.spawned),
    fallos,
  }
}

/**
 * Que hace cada agente, leido de .claude/agents/*.md.
 *
 * La vista de la cuenta dice que un modelo es "el que juzga" y otro "el que
 * escribe". Eso no se escribe a mano aqui: sale del frontmatter de los
 * agentes, que es donde vive de verdad. El dia que el revisor cambie de
 * modelo, la pantalla lo cuenta sola.
 */
export type ModeloDeAgente = { agente: string; modelo: string; juzga: boolean }

const JUECES = new Set(['revisor', 'verificador'])

export function leerModelosDeAgentes(archivos: Record<string, string>): ModeloDeAgente[] {
  const salida: ModeloDeAgente[] = []
  for (const [ruta, crudo] of Object.entries(archivos)) {
    const nombre = ruta.split('/').pop()?.replace(/\.md$/, '') ?? ''
    const m = crudo.replace(/\r\n/g, '\n').match(/^---\n([\s\S]*?)\n---/)
    if (!m) continue
    const modelo = m[1].match(/^model:\s*(\S+)\s*$/m)?.[1]
    if (!modelo) continue
    salida.push({ agente: nombre, modelo, juzga: JUECES.has(nombre) })
  }
  return salida.sort((a, b) => a.agente.localeCompare(b.agente))
}

/**
 * El rotulo de un modelo en la vista de la cuenta: "los que juzgan" o "los que
 * escriben", segun que agentes lo usen. Si ningun agente lo declara, el modelo
 * se ensena sin rotulo en vez de con uno adivinado.
 */
export function rotuloDeModelo(modelo: string, agentes: ModeloDeAgente[]): string | null {
  const suyos = agentes.filter((a) => modelo.startsWith(a.modelo) || modelo.includes(a.modelo))
  if (suyos.length === 0) return null
  const juzgan = suyos.filter((a) => a.juzga).length
  if (juzgan === suyos.length) return 'los que juzgan'
  if (juzgan === 0) return 'los que escriben'
  return null
}
