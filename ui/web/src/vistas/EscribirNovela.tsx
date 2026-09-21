// Escribir una novela nueva, y mirarla nacer.
//
// Esta pestana es la unica del tablero que provoca algo. Y aun asi no
// orquesta: manda un prompt a Claude Code y se aparta. Lo que se pinta de la
// novela sale de la carpeta, igual que en el historial; del stream solo sale
// que agente esta encendido en este segundo, que es lo unico que la carpeta no
// puede contar.

import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'

import type { Carga, Fuente } from '../datos/fuente.ts'
import { duracion } from '../diseno/formato.ts'
import type { Capitulo } from '../lector/index.ts'
import { Grafo } from '../piezas/Grafo.tsx'
import { Papel } from '../piezas/Papel.tsx'
import { RejillaLuces } from '../piezas/RejillaLuces.tsx'
import { filasEnVivo, rotuloDe, trabajandoAhora } from '../reloj/envivo.ts'

type Seleccion = { tipo: 'capitulo'; numero: number } | { tipo: 'novela' } | null

export function EscribirNovela({ fuente, carga }: { fuente: Fuente | null; carga: Carga }) {
  const { corrida, novela } = carga
  const [seleccion, setSeleccion] = useState<Seleccion>(null)
  const [otra, setOtra] = useState(false)

  // Al arrancar una corrida nueva se sale del formulario solo.
  const empezada = corrida?.empezada ?? 0
  useEffect(() => {
    if (empezada) setOtra(false)
  }, [empezada])

  const aprobados = (novela?.capitulos ?? []).filter((c) => c.estado === 'aprobado')
  const cierre = novela?.cierre ?? null

  // Lo que va apareciendo se abre solo: primero cada capitulo en cuanto entra,
  // y al final la novela entera. Si el usuario ha elegido algo a mano, no se
  // le quita de delante.
  const tocado = useRef(false)
  const ultimoAprobado = aprobados.at(-1)?.numero ?? null
  useEffect(() => {
    if (tocado.current) return
    if (cierre) setSeleccion({ tipo: 'novela' })
    else if (ultimoAprobado !== null) setSeleccion({ tipo: 'capitulo', numero: ultimoAprobado })
  }, [ultimoAprobado, cierre])

  const elegir = (s: Seleccion) => {
    tocado.current = true
    setSeleccion(s)
  }

  if (!corrida || otra) return <Formulario fuente={fuente} />

  return (
    <div className="flex min-h-0 flex-1">
      <section className="flex w-[46%] shrink-0 flex-col border-r border-borde">
        <Encabezado corrida={corrida} fuente={fuente} alOtra={() => setOtra(true)} />

        <div className="flex min-h-0 flex-1 items-center justify-center px-6">
          <div className="h-[19rem] w-full max-w-[40rem]">
            <Grafo
              trabajando={trabajandoAhora(corrida.activos)}
              hayPlan={(novela?.capitulosPrevistos.length ?? 0) > 0}
            />
          </div>
        </div>

        <div className="h-[38%] shrink-0 border-t border-borde p-4">
          <RejillaLuces filas={filasEnVivo(novela, corrida.activos)} />
        </div>
      </section>

      <section className="flex min-w-0 flex-1 flex-col">
        <Tiras
          capitulos={novela?.capitulos ?? []}
          previstos={novela?.capitulosPrevistos.length ?? 0}
          hayCierre={cierre !== null}
          seleccion={seleccion}
          alElegir={elegir}
        />
        <Lectura novela={novela} seleccion={seleccion} corrida={corrida} />
      </section>
    </div>
  )
}

// --- el formulario -------------------------------------------------------

function Formulario({ fuente }: { fuente: Fuente | null }) {
  const [idea, setIdea] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const puede = fuente?.lanzar != null

  const lanzar = async () => {
    if (!puede || !idea.trim() || enviando) return
    setEnviando(true)
    setError(null)
    try {
      await fuente!.lanzar!(idea.trim())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center px-12">
      <div className="w-full max-w-3xl">
        <h2 className="font-[family-name:var(--font-libro)] text-[26px] text-texto">
          ¿Qué novela quieres?
        </h2>
        <p className="mt-2 font-[family-name:var(--font-maquina)] text-[12px] leading-relaxed text-texto-suave">
          Cuéntalo con tus palabras, y di ahí mismo cuánto quieres que dure. La longitud es una
          instrucción para el arquitecto, no una casilla del tablero: cabe decir «tres capítulos de
          unas 700 palabras» igual que «algo corto, que se lea de una sentada».
        </p>

        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void lanzar()
          }}
          rows={5}
          autoFocus
          disabled={!puede || enviando}
          placeholder="Un portero de discoteca de Vigo descubre que su hermano lleva diez años pagándole el alquiler sin decírselo. Unas 2500 palabras, en cuatro capítulos de unas 600."
          className="mt-5 w-full resize-none rounded-sm border border-borde bg-superficie px-4 py-3 font-[family-name:var(--font-libro)] text-[15px] leading-relaxed text-texto placeholder:text-texto-suave/70 focus:border-naranja focus:outline-none disabled:opacity-50"
        />

        <div className="mt-4 flex items-center gap-4">
          <button
            type="button"
            onClick={() => void lanzar()}
            disabled={!puede || enviando || idea.trim() === ''}
            className="rounded-sm bg-naranja px-5 py-2 font-[family-name:var(--font-maquina)] text-[12px] tracking-[0.14em] text-white disabled:opacity-40"
          >
            {enviando ? 'arrancando…' : 'escribir la novela'}
          </button>
          <span className="font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
            ⌘/Ctrl + Enter · tarda entre 15 y 25 minutos y cuesta unos 3 USD
          </span>
        </div>

        {!puede && (
          <p className="mt-5 rounded-sm border border-dashed border-borde p-4 font-[family-name:var(--font-maquina)] text-[11px] leading-relaxed text-texto-suave">
            Esto necesita el servidor: abierto con doble clic, el tablero solo reproduce corridas
            que ya pasaron. Arráncalo con <span className="text-texto">npm run dev</span>.
          </p>
        )}

        {error && (
          <p className="mt-5 font-[family-name:var(--font-maquina)] text-[12px] text-naranja">
            {error}
          </p>
        )}
      </div>
    </div>
  )
}

// --- mientras escribe ----------------------------------------------------

function Encabezado({
  corrida,
  fuente,
  alOtra,
}: {
  corrida: NonNullable<Carga['corrida']>
  fuente: Fuente | null
  alOtra: () => void
}) {
  const [ahora, setAhora] = useState(Date.now())
  useEffect(() => {
    if (corrida.terminada) return
    const t = setInterval(() => setAhora(Date.now()), 1000)
    return () => clearInterval(t)
  }, [corrida.terminada])

  return (
    <div className="shrink-0 border-b border-borde px-6 py-3">
      <p className="truncate font-[family-name:var(--font-libro)] text-[14px] text-texto-suave italic">
        «{corrida.idea}»
      </p>
      <div className="mt-2 flex items-baseline gap-4">
        <span className="font-[family-name:var(--font-maquina)] text-[20px] leading-none tabular-nums text-texto">
          {duracion(ahora - corrida.empezada)}
        </span>
        <span
          className={
            'min-w-0 flex-1 truncate font-[family-name:var(--font-maquina)] text-[11px] ' +
            (corrida.activos.length > 0 ? 'text-naranja' : 'text-texto-suave')
          }
        >
          {corrida.terminada ? corrida.rotulo : rotuloDe(corrida.activos, corrida.rotulo)}
        </span>

        {corrida.terminada ? (
          <button
            type="button"
            onClick={alOtra}
            className="shrink-0 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave underline decoration-borde underline-offset-4 hover:text-texto"
          >
            escribir otra
          </button>
        ) : (
          fuente?.parar && (
            <button
              type="button"
              onClick={() => void fuente.parar!()}
              className="shrink-0 rounded-sm border border-borde px-2 py-0.5 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave hover:border-naranja hover:text-naranja"
            >
              parar
            </button>
          )
        )}
      </div>
    </div>
  )
}

/**
 * Lo que dijo Claude Code cuando se murio.
 *
 * Entero y sin recortar. Un error de una linea cortada con puntos suspensivos
 * no se puede arreglar, y aqui el usuario acaba de gastar tiempo -y quiza
 * dinero- en algo que no salio.
 */
function Fallo({ texto }: { texto: string }) {
  return (
    <div className="mx-auto max-w-lg px-8">
      <p className="font-[family-name:var(--font-maquina)] text-[12px] tracking-wide text-naranja">
        la corrida no llegó a escribir nada
      </p>
      <pre className="mt-3 font-[family-name:var(--font-maquina)] text-[11px] leading-relaxed whitespace-pre-wrap text-texto-suave">
        {texto}
      </pre>
    </div>
  )
}

function Tiras({
  capitulos,
  previstos,
  hayCierre,
  seleccion,
  alElegir,
}: {
  capitulos: Capitulo[]
  previstos: number
  hayCierre: boolean
  seleccion: Seleccion
  alElegir: (s: Seleccion) => void
}) {
  const aprobados = capitulos.filter((c) => c.estado === 'aprobado')
  const faltan = Math.max(0, previstos - capitulos.length)

  return (
    <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-borde px-6 py-3">
      <AnimatePresence initial={false}>
        {capitulos.map((c) => {
          const elegido = seleccion?.tipo === 'capitulo' && seleccion.numero === c.numero
          const entro = c.estado === 'aprobado'
          return (
            <motion.button
              key={c.numero}
              layout
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, ease: [0.2, 0, 0, 1] }}
              type="button"
              onClick={() => alElegir({ tipo: 'capitulo', numero: c.numero })}
              className={
                'rounded-sm border px-3 py-1.5 font-[family-name:var(--font-maquina)] text-[11px] ' +
                (elegido
                  ? 'border-naranja text-texto'
                  : entro
                    ? 'border-borde text-texto-suave hover:text-texto'
                    : 'border-dashed border-borde text-texto-suave')
              }
            >
              cap {String(c.numero).padStart(2, '0')}
              <span className={entro ? 'ml-2 text-verde' : 'ml-2 opacity-60'}>
                {entro ? '✓' : '…'}
              </span>
            </motion.button>
          )
        })}
      </AnimatePresence>

      {Array.from({ length: faltan }, (_, i) => (
        <span
          key={`falta-${i}`}
          className="rounded-sm border border-dashed border-borde/50 px-3 py-1.5 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave/50"
        >
          cap {String(capitulos.length + i + 1).padStart(2, '0')}
        </span>
      ))}

      {hayCierre && (
        <motion.button
          layout
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.32, ease: [0.2, 0, 0, 1] }}
          type="button"
          onClick={() => alElegir({ tipo: 'novela' })}
          className={
            'ml-2 rounded-sm px-3 py-1.5 font-[family-name:var(--font-maquina)] text-[11px] tracking-wide ' +
            (seleccion?.tipo === 'novela'
              ? 'bg-naranja text-white'
              : 'border border-naranja text-naranja')
          }
        >
          la novela entera
        </motion.button>
      )}

      <span className="ml-auto font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
        {aprobados.length} de {previstos || capitulos.length} capítulos
      </span>
    </div>
  )
}

function Lectura({
  novela,
  seleccion,
  corrida,
}: {
  novela: Carga['novela']
  seleccion: Seleccion
  corrida: NonNullable<Carga['corrida']>
}) {
  // Hasta que haya prosa, el panel se queda oscuro. Un folio en blanco a
  // pantalla completa sobre un tablero oscuro deslumbra en el video, y ademas
  // promete algo que todavia no existe.
  if (!novela || seleccion === null) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto py-8">
        {corrida.fallo ? (
          <Fallo texto={corrida.fallo} />
        ) : (
          <p className="max-w-sm px-8 text-center font-[family-name:var(--font-maquina)] text-[12px] leading-relaxed text-texto-suave">
            {corrida.terminada
              ? 'la corrida terminó sin dejar capítulos en disco'
              : 'todavía no hay nada escrito. El primer capítulo aparecerá aquí en cuanto pase las dos luces.'}
          </p>
        )}
      </div>
    )
  }

  const texto =
    seleccion.tipo === 'novela'
      ? novela.cierre
      : (novela.capitulos.find((c) => c.numero === seleccion.numero)?.texto ?? null)

  const capitulo =
    seleccion.tipo === 'capitulo'
      ? (novela.capitulos.find((c) => c.numero === seleccion.numero) ?? null)
      : null

  return <Papel texto={texto} capitulo={capitulo} esNovela={seleccion.tipo === 'novela'} />
}
