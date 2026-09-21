// El lanzador ejecuta el mismo Claude Code que se usaria desde la terminal.
//
// El tablero no orquesta. No despacha agentes, no lee luces y no renombra
// nada: escribe un prompt y se aparta. Si el lanzador hiciera un solo paso del
// ciclo, la capa dejaria de ser una capa, y seria exactamente la UI que se
// borro en d42c084.
//
// La verdad es el vigia, no el stream. Lo que se pinta de la novela sale de
// los archivos. Del stream solo sale **quien esta trabajando ahora mismo**,
// que es lo unico que la carpeta no puede contar: un agente despachado no deja
// rastro en disco hasta que termina. Si el formato del stream cambia en una
// version de Claude Code, se apagan los nodos y el resto del tablero sigue
// funcionando igual.

import { spawn, type ChildProcess, type SpawnOptions } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

/**
 * Los permisos con los que corre Claude Code.
 *
 * En modo `--print` no hay nadie a quien preguntarle si puede escribir un
 * archivo, asi que sin esto todo lo que necesita permiso se deniega solo y la
 * corrida muere a los diez segundos sin haber escrito nada.
 *
 * La skill `dirigir-novela` necesita Bash (mkdir, mv, sed, grep, wc), Write y
 * Read para los agentes, y Agent para despacharlos. Se nombran uno por uno en
 * vez de saltarse los permisos enteros: esto corre sobre el repositorio de
 * alguien, no en una caja de arena.
 */
const PERMISOS = [
  '--permission-mode',
  'acceptEdits',
  '--allowedTools',
  'Bash,Read,Write,Edit,Glob,Grep,Agent,Task',
  // Nadie va a contestar un dialogo: lo que aun asi preguntase, se deniega.
  '--permission-prompts',
  'none',
]

/** Como se invoca al ejecutable sin que Windows destroce los argumentos. */
type Invocacion = { orden: string; args: string[]; opciones: SpawnOptions }

function entrecomillar(s: string): string {
  return /[\s"&|<>^()]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function invocacion(ejecutable: string, args: string[]): Invocacion {
  // Un .exe se lanza directo, sin shell: los argumentos llegan enteros aunque
  // lleven espacios, comillas o tildes.
  if (!/\.(cmd|bat)$/i.test(ejecutable)) {
    return { orden: ejecutable, args, opciones: {} }
  }
  // Un .cmd no se puede lanzar sin cmd.exe en Windows. La linea se monta a
  // mano y se pasa tal cual, en vez de dejar que Node concatene sin escapar:
  // con `shell: true`, una idea con espacios llega partida en trozos y Claude
  // Code recibe media frase como prompt y el resto como flags que no conoce.
  const linea = [ejecutable, ...args].map(entrecomillar).join(' ')
  return {
    orden: process.env.ComSpec ?? 'cmd.exe',
    args: ['/d', '/s', '/c', `"${linea}"`],
    opciones: { windowsVerbatimArguments: true },
  }
}

/** Un subagente que esta corriendo ahora mismo. */
export type Despachado = {
  id: string
  agente: string
  /** La `description` del despacho: "redactor · cap 03 · intento 2". */
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
  /** Lo ultimo que se le entendio al stream. */
  rotulo: string | null
  terminada: boolean
  /** Si el proceso murio mal, el motivo. */
  fallo: string | null
}

type Corrida = EstadoCorrida & {
  proceso: ChildProcess
  despachos: Map<string, Despachado>
  resto: string
  /** Lo que se haya quejado por la salida de error, por si hace falta. */
  quejas: string
  /** Si llego a despachar a alguien. Si no, la corrida no arranco de verdad. */
  hubo: boolean
  /** La paro una persona. No es un fallo y no se cuenta como tal. */
  parada: boolean
}

// Una corrida a la vez. Dos novelas en paralelo escribiendo en books/ hacen
// ilegible el vigia y no aportan nada.
let actual: Corrida | null = null
let avisar: (() => void) | null = null

/** Quien quiera enterarse de que cambio el estado de la corrida. */
export function alCambiarCorrida(f: () => void): void {
  avisar = f
}

export function estadoDeCorrida(): EstadoCorrida | null {
  if (!actual) return null
  return {
    slug: actual.slug,
    idea: actual.idea,
    empezada: actual.empezada,
    activos: [...actual.despachos.values()].sort((a, b) => a.desde - b.desde),
    rotulo: actual.rotulo,
    terminada: actual.terminada,
    fallo: actual.fallo,
  }
}

export function loQueCorre(): { slug: string } | null {
  return actual && !actual.terminada ? { slug: actual.slug } : null
}

/**
 * Donde esta el ejecutable de Claude Code.
 *
 * En Windows `claude` suele ser un .cmd, asi que el spawn va con shell. Y
 * puede no estar en el PATH: en esta maquina, por ejemplo, vive dentro de la
 * extension de VSCode. STORY_MAKER_CLAUDE permite senalarlo a mano, y
 * /api/salud lo comprueba al arrancar, que es mucho mejor que descubrirlo
 * mientras se graba.
 */
export function rutaDeClaude(): string | null {
  const declarada = process.env.STORY_MAKER_CLAUDE
  if (declarada && existsSync(declarada)) return declarada

  const carpetas = (process.env.PATH ?? '').split(path.delimiter).filter(Boolean)
  const nombres =
    process.platform === 'win32' ? ['claude.cmd', 'claude.exe', 'claude.bat'] : ['claude']

  for (const carpeta of carpetas) {
    for (const nombre of nombres) {
      const candidata = path.join(carpeta, nombre)
      if (existsSync(candidata)) return candidata
    }
  }
  return null
}

/**
 * Lanza una novela.
 *
 * El prompt es la idea del usuario tal cual, sin nada anadido. La longitud, si
 * la hay, va dentro de esa idea: es una instruccion para el arquitecto, no un
 * parametro del tablero, y la skill ya sabe que hacer si no viene ninguna.
 */
export function lanzar(raizRepo: string, idea: string): EstadoCorrida {
  if (actual && !actual.terminada) {
    throw new Error(`ya hay una corrida en marcha (${actual.slug})`)
  }

  const ejecutable = rutaDeClaude()
  if (!ejecutable) {
    throw new Error(
      'no encuentro el ejecutable de Claude Code. Ponlo en el PATH o declara STORY_MAKER_CLAUDE con su ruta completa.',
    )
  }

  const { orden, args, opciones } = invocacion(ejecutable, [
    '-p',
    idea,
    '--output-format',
    'stream-json',
    '--verbose',
    ...PERMISOS,
  ])

  const proceso = spawn(orden, args, {
    cwd: raizRepo,
    windowsHide: true,
    // La entrada se cierra de entrada. Si se le deja un tubo abierto que nadie
    // escribe, Claude Code espera tres segundos por si le llega el prompt por
    // ahi y avisa por la salida de error: ruido que parece un fallo y no lo es.
    stdio: ['ignore', 'pipe', 'pipe'],
    ...opciones,
  })

  const corrida: Corrida = {
    // Todavia no se sabe: el slug lo elige la skill. En cuanto aparezca una
    // carpeta nueva en books/, el servidor la adopta.
    slug: '',
    idea,
    empezada: Date.now(),
    activos: [],
    rotulo: 'arrancando Claude Code…',
    terminada: false,
    fallo: null,
    proceso,
    despachos: new Map(),
    resto: '',
    quejas: '',
    hubo: false,
    parada: false,
  }
  actual = corrida

  proceso.stdout?.setEncoding('utf8')
  proceso.stdout?.on('data', (trozo: string) => {
    corrida.resto += trozo
    const lineas = corrida.resto.split('\n')
    corrida.resto = lineas.pop() ?? ''
    let cambio = false
    for (const linea of lineas) if (leerLinea(corrida, linea)) cambio = true
    if (cambio) avisar?.()
  })

  // Una queja por la salida de error no es un fallo: Claude Code avisa de
  // cosas por ahi y la corrida sigue. Se guarda por si al final hace falta
  // explicar por que murio, y se ensena solo entonces.
  proceso.stderr?.setEncoding('utf8')
  proceso.stderr?.on('data', (trozo: string) => {
    corrida.quejas = (corrida.quejas + trozo).slice(-1200)
  })

  proceso.on('close', (codigo) => {
    corrida.terminada = true
    corrida.despachos.clear()
    if (corrida.parada) {
      // La paro una persona: ni el codigo de salida ni las quejas cuentan como
      // un fallo, porque el fallo seria decir que fallo algo.
      corrida.rotulo = 'parado a mano'
      avisar?.()
      return
    }
    corrida.rotulo = codigo === 0 ? 'terminado' : `terminado con codigo ${codigo}`
    if (!corrida.fallo) {
      if (codigo !== 0) {
        corrida.fallo = corrida.quejas.trim() || `Claude Code terminó con código ${codigo}.`
      } else if (!corrida.hubo) {
        // Termino bien y sin despachar a nadie: no escribio la novela. Decirlo
        // es mas util que dejar la pantalla vacia diciendo "terminado".
        corrida.fallo =
          'Claude Code terminó sin despachar un solo agente, así que no llegó a empezar la novela. ' +
          (corrida.quejas.trim() || 'No dijo por qué.')
      }
    }
    avisar?.()
  })
  proceso.on('error', (e) => {
    corrida.terminada = true
    corrida.fallo = e.message
    avisar?.()
  })

  // Avisar ya, sin esperar al stream. Claude Code tarda cerca de un minuto en
  // despachar al primer agente -arranca, lee la skill, piensa el plan- y hasta
  // entonces no emite nada que cambie el estado. Sin este aviso, quien le dio
  // al boton se queda un minuto mirando el formulario sin saber si pasó algo.
  avisar?.()
  return estadoDeCorrida()!
}

export function parar(): void {
  if (!actual || actual.terminada) return
  actual.parada = true
  actual.proceso.kill()
  actual.terminada = true
  actual.despachos.clear()
  actual.rotulo = 'parado a mano'
  avisar?.()
}

/**
 * Si aparece una novela que no existia mientras hay una corrida, esa es la
 * corrida: la skill elige el slug y el tablero se entera mirando la carpeta.
 */
export function adoptarSlug(slug: string): void {
  if (actual && !actual.terminada && actual.slug === '') {
    actual.slug = slug
    avisar?.()
  }
}

// --- el stream -----------------------------------------------------------

const DESCRIPCION = /cap\s*(\d+)/i
const INTENTO = /intento\s*(\d+)/i

/** Devuelve true si esta linea cambio algo que se ve en pantalla. */
function leerLinea(corrida: Corrida, linea: string): boolean {
  const l = linea.trim()
  if (!l.startsWith('{')) return false

  let evento: Record<string, unknown>
  try {
    evento = JSON.parse(l) as Record<string, unknown>
  } catch {
    // Una linea a medias del stream no es un error.
    return false
  }

  if (evento.type === 'result') {
    corrida.despachos.clear()
    corrida.rotulo = 'cerrando'
    const malo = evento.is_error === true || (evento.subtype && evento.subtype !== 'success')
    if (malo) {
      const dicho = typeof evento.result === 'string' ? evento.result : ''
      corrida.fallo = (dicho || `Claude Code devolvió "${String(evento.subtype)}".`).slice(0, 800)
    }
    return true
  }

  const mensaje = evento.message as { content?: unknown[] } | undefined
  const contenido = mensaje?.content
  if (!Array.isArray(contenido)) return false

  let cambio = false
  for (const parte of contenido) {
    const p = parte as Record<string, unknown>

    // Un despacho: se enciende el agente.
    if (p.type === 'tool_use') {
      const entrada = (p.input ?? {}) as Record<string, unknown>
      const agente = entrada.subagent_type
      // Cualquier herramienta con subagent_type es un despacho, se llame como
      // se llame. Atarlo al nombre de la herramienta lo rompe en cuanto
      // cambie.
      if (typeof agente !== 'string' || typeof p.id !== 'string') continue
      const descripcion = typeof entrada.description === 'string' ? entrada.description : agente
      corrida.despachos.set(p.id, {
        id: p.id,
        agente,
        descripcion,
        capitulo: numeroDe(descripcion, DESCRIPCION),
        intento: numeroDe(descripcion, INTENTO),
        desde: Date.now(),
      })
      corrida.rotulo = descripcion
      corrida.hubo = true
      cambio = true
      continue
    }

    // Su resultado: se apaga.
    if (p.type === 'tool_result' && typeof p.tool_use_id === 'string') {
      if (corrida.despachos.delete(p.tool_use_id)) cambio = true
    }
  }
  return cambio
}

function numeroDe(texto: string, patron: RegExp): number | null {
  const m = texto.match(patron)
  return m ? Number(m[1]) : null
}
