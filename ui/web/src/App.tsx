// El tablero.
//
// Dos pestanas: el historial, que lee corridas que ya pasaron, y escribir, que
// pide una novela nueva y la mira nacer. Dentro del historial, todo el
// recorrido se hace sin raton, para que el video salga de una toma y no se vea
// el cursor buscando un boton.

import { useEffect, useMemo, useRef, useState } from 'react'

import { elegirFuente } from './datos/fuente.ts'
import type { Carga, Fuente } from './datos/fuente.ts'
import type { Resumen } from './lector/index.ts'
import { BarraDesarrollo } from './piezas/BarraDesarrollo.tsx'
import { Cabecera, type Etiquetado } from './piezas/Cabecera.tsx'
import { instanteEn } from './reloj/guion.ts'
import { usarTablero, type Tablero } from './reloj/store.ts'
import { ElCirculo } from './vistas/ElCirculo.tsx'
import { ElExpediente } from './vistas/ElExpediente.tsx'
import { EscribirNovela } from './vistas/EscribirNovela.tsx'
import { LaCuenta } from './vistas/LaCuenta.tsx'

const VACIA: Carga = { novela: null, corrida: null }

/**
 * Con que novela se abre el historial.
 *
 * Tiene que ser una que este medida. El video tiene que dejar dicho que esto
 * cuesta dinero y que el dinero esta medido, y una novela sin sesion.json deja
 * dos de las tres vistas diciendo "sin medir": la correcta, y vacia. Entre las
 * medidas se elige la que mas intentos tenga, que es la que mas veces ensena
 * el ciclo funcionando.
 */
function novelaDeApertura(lista: Resumen[]): string | null {
  const medidas = lista.filter((r) => r.costeUSD !== null)
  const candidatas = medidas.length > 0 ? medidas : lista
  const mejor = [...candidatas].sort(
    (a, b) => b.intentos - a.intentos || a.slug.localeCompare(b.slug),
  )[0]
  return mejor?.slug ?? null
}

export function App() {
  const [fuente, setFuente] = useState<Fuente | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const [resumenes, setResumenes] = useState<Resumen[]>([])
  const [slug, setSlug] = useState<string | null>(null)
  /** Lo que se esta escribiendo ahora, para la pestana de escribir. */
  const [escritura, setEscritura] = useState<Carga>(VACIA)

  const t = usarTablero()

  // --- de donde salen los acontecimientos --------------------------------
  useEffect(() => {
    let vivo = true
    elegirFuente()
      .then(async (f) => {
        if (!vivo) return
        setFuente(f)
        const lista = await f.listar()
        if (!vivo) return
        setResumenes(lista)
        setSlug(novelaDeApertura(lista))
        usarTablero.getState().ponerAgentes(await f.agentes())
      })
      .catch((e: unknown) => setFallo(e instanceof Error ? e.message : String(e)))
    return () => {
      vivo = false
    }
  }, [])

  // --- la novela del historial, y sus cambios ----------------------------
  useEffect(() => {
    if (!fuente || !slug) return
    let vivo = true

    const poner = (carga: Carga) => {
      if (!vivo || !carga.novela) return
      const enMarcha = carga.corrida !== null && !carga.corrida.terminada
      usarTablero.getState().ponerNovela(carga.novela, enMarcha ? 'vivo' : 'replay')
    }

    fuente
      .abrir(slug)
      .then((n) => poner({ novela: n, corrida: null }))
      .catch((e: unknown) => setFallo(e instanceof Error ? e.message : String(e)))

    const baja = fuente.seguir(slug, poner)
    return () => {
      vivo = false
      baja()
    }
  }, [fuente, slug])

  // --- la novela que se escribe ahora ------------------------------------
  //
  // Suscripcion aparte y siempre abierta: al lanzar todavia no hay slug -lo
  // elige la skill- y ademas hay que enterarse de que una corrida arranco
  // aunque estemos mirando el historial.
  useEffect(() => {
    if (!fuente) return
    const baja = fuente.seguirLaQueSeEscribe(setEscritura)
    void fuente.salud().then((s) => {
      if (s?.corrida) setEscritura((a) => (a.corrida ? a : { novela: null, corrida: s.corrida }))
    })
    return baja
  }, [fuente])

  // Cuando la novela nueva ya tiene carpeta, entra en la lista de corridas.
  const slugEscrito = escritura.corrida?.slug ?? ''
  useEffect(() => {
    if (!fuente || !slugEscrito) return
    void fuente.listar().then(setResumenes)
  }, [fuente, slugEscrito, escritura.corrida?.terminada])

  // --- el teclado ---------------------------------------------------------
  const estado = useRef({ vista: t.vista, pestana: t.pestana })
  estado.current = { vista: t.vista, pestana: t.pestana }

  useEffect(() => {
    const alPulsar = (e: KeyboardEvent) => {
      const destino = e.target as HTMLElement | null
      if (destino && /^(INPUT|TEXTAREA|SELECT)$/.test(destino.tagName)) return

      const s = usarTablero.getState()
      const { vista, pestana } = estado.current

      switch (e.key) {
        // Los digitos llevan preventDefault porque la pestana de escribir
        // enfoca su textarea al montarse: sin esto, la misma pulsacion que
        // cambia de pestana se escribe dentro del campo.
        case '1':
          e.preventDefault()
          s.irA('circulo')
          break
        case '2':
          e.preventDefault()
          s.irA('expediente')
          break
        case '3':
          e.preventDefault()
          s.irA('cuenta')
          break
        case '4':
          e.preventDefault()
          s.irAPestana('escribir')
          break
        case ' ':
          if (pestana !== 'historial') return
          e.preventDefault()
          s.alternarReproduccion()
          break
        case 'ArrowRight':
          if (pestana !== 'historial') return
          e.preventDefault()
          // En el expediente las flechas pasan de capitulo, que es lo que esa
          // vista tiene de movimiento; en las otras dos mueven el guion.
          if (vista === 'expediente') moverCapitulo(1)
          else s.adelante()
          break
        case 'ArrowLeft':
          if (pestana !== 'historial') return
          e.preventDefault()
          if (vista === 'expediente') moverCapitulo(-1)
          else s.atras()
          break
        case '+':
        case '=':
          s.cambiarVelocidad(1)
          break
        case '-':
          s.cambiarVelocidad(-1)
          break
        case 'g':
        case 'G':
          s.alternarGrabacion()
          break
        case 'c':
        case 'C':
          if (pestana === 'historial' && vista === 'expediente') s.alternarCrudo()
          break
      }
    }
    window.addEventListener('keydown', alPulsar)
    return () => window.removeEventListener('keydown', alPulsar)
  }, [])

  // --- el modo grabacion --------------------------------------------------
  useEffect(() => {
    document.body.dataset.grabacion = t.modoGrabacion ? 'si' : 'no'
  }, [t.modoGrabacion])

  // --- lo que se ve -------------------------------------------------------
  const instante = useMemo(
    () => (t.novela ? instanteEn(t.novela, t.guion, t.indice) : null),
    [t.novela, t.guion, t.indice],
  )

  // Mientras el replay corre, el expediente sigue al capitulo que toca: asi el
  // salto de la vista 1 a la 2 cae ya en el capitulo del que se acaba de
  // hablar, sin buscarlo a mano delante de la camara.
  const capituloEnCurso = instante?.capitulo ?? null
  useEffect(() => {
    if (t.corriendo && capituloEnCurso !== null) {
      usarTablero.getState().abrirCapitulo(capituloEnCurso)
    }
  }, [t.corriendo, capituloEnCurso])

  if (fallo) return <Fallo mensaje={fallo} />

  const corriendoAhora =
    escritura.corrida !== null && !escritura.corrida.terminada ? escritura.corrida.slug : null

  const etiquetado: Etiquetado =
    t.pestana === 'escribir'
      ? corriendoAhora !== null
        ? 'vivo'
        : 'espera'
      : t.modo === 'vivo'
        ? 'vivo'
        : 'replay'

  const marco = (dentro: React.ReactNode) => (
    <Marco grabacion={t.modoGrabacion}>
      <Cabecera
        pestana={t.pestana}
        vista={t.vista}
        derecha={derechaDe(t, escritura)}
        etiquetado={etiquetado}
        origen={fuente?.origen ?? '—'}
        grabacion={t.modoGrabacion}
        puedeEscribir={fuente?.lanzar != null}
        alPestana={(p) => usarTablero.getState().irAPestana(p)}
        alVista={(v) => usarTablero.getState().irA(v)}
      />
      {dentro}
    </Marco>
  )

  if (t.pestana === 'escribir') {
    return marco(<EscribirNovela fuente={fuente} carga={escritura} />)
  }

  if (!t.novela || !instante) return marco(<Cargando />)

  const capitulo =
    t.novela.capitulos.find((c) => c.numero === t.capituloAbierto) ?? t.novela.capitulos[0] ?? null

  return marco(
    <>
      {t.vista === 'circulo' && <ElCirculo novela={t.novela} instante={instante} />}
      {t.vista === 'expediente' && (
        <ElExpediente
          novela={t.novela}
          capitulo={capitulo}
          alCambiarCapitulo={(n) => usarTablero.getState().abrirCapitulo(n)}
          verCierre={t.verCierre}
          alVerCierre={(ver) =>
            ver
              ? usarTablero.getState().abrirCierre()
              : usarTablero.getState().abrirCapitulo(capitulo?.numero ?? 1)
          }
          verCrudo={t.verCrudo}
          alAlternarCrudo={() => usarTablero.getState().alternarCrudo()}
        />
      )}
      {t.vista === 'cuenta' && (
        <LaCuenta novela={t.novela} resumenes={resumenes} agentes={t.agentes} />
      )}

      <BarraDesarrollo
        resumenes={resumenes}
        slug={slug}
        alElegir={setSlug}
        escribiendo={corriendoAhora}
      />
    </>,
  )
}

function derechaDe(t: Tablero, escritura: Carga): string {
  if (t.pestana === 'escribir') {
    const c = escritura.corrida
    if (!c) return 'sin nada en marcha'
    return [c.slug || 'eligiendo nombre…', c.terminada ? 'terminada' : 'escribiendo']
      .filter(Boolean)
      .join(' · ')
  }
  if (!t.novela) return ''
  const intentos = t.novela.capitulos.reduce((n, c) => n + c.intentos.length, 0)
  if (t.vista === 'circulo') return t.novela.slug
  if (t.vista === 'expediente') {
    return `${t.novela.slug} · ${t.novela.capitulos.length} capítulos · ${intentos} intentos`
  }
  return `${t.novela.slug} · ${t.novela.capitulos.length} caps`
}

function moverCapitulo(paso: number) {
  const s = usarTablero.getState()
  if (!s.novela) return
  const numeros = s.novela.capitulos.map((c) => c.numero)
  const i = numeros.indexOf(s.capituloAbierto ?? numeros[0])
  const siguiente = numeros[Math.min(numeros.length - 1, Math.max(0, i + paso))]
  if (siguiente !== undefined) s.abrirCapitulo(siguiente)
}

/**
 * El modo grabacion bloquea el ancho a 16:9: el video se graba a 1920x1080 y
 * lo que no cabe no existe.
 */
function Marco({ grabacion, children }: { grabacion: boolean; children: React.ReactNode }) {
  if (!grabacion) return <div className="flex h-full flex-col">{children}</div>
  return (
    <div className="flex h-full items-center justify-center bg-black">
      <div
        className="flex flex-col overflow-hidden bg-fondo"
        style={{ aspectRatio: '16 / 9', width: 'min(100vw, calc(100vh * 16 / 9))', height: 'auto' }}
      >
        <div className="flex h-full flex-col">{children}</div>
      </div>
    </div>
  )
}

function Cargando() {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
      leyendo books/…
    </div>
  )
}

function Fallo({ mensaje }: { mensaje: string }) {
  return (
    <div className="flex h-full items-center justify-center px-12">
      <div className="max-w-xl">
        <p className="font-[family-name:var(--font-maquina)] text-[12px] text-naranja">
          el tablero no ha podido leer nada
        </p>
        <p className="mt-2 font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
          {mensaje}
        </p>
      </div>
    </div>
  )
}
