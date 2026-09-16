import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'

/**
 * El flujo de trabajo: quien trabaja, en que orden, con que herramientas y
 * contra que regla. A la izquierda lo DECLARADO (harness/flujo.yaml), a la
 * derecha lo que REALMENTE paso en un libro.
 *
 * Que sean dos columnas es el punto: un diagrama que no se compara con la
 * ejecucion es documentacion, y la documentacion se desactualiza sola.
 */
export default function Flujo({ libros }) {
  const [flujo, setFlujo] = useState(null)
  const [slug, setSlug] = useState('')
  const [traza, setTraza] = useState({ eventos: [], resumen: null })
  const [error, setError] = useState('')

  useEffect(() => {
    api.flujo().then(setFlujo).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!slug) return setTraza({ eventos: [], resumen: null })
    api.traza(slug).then(setTraza).catch((e) => setError(e.message))
  }, [slug])

  // Cuantas veces corrio cada agente en el libro elegido, para cruzar lo
  // declarado con lo ejecutado.
  const corridas = useMemo(() => {
    const m = {}
    for (const ev of traza.eventos) {
      const k = ev.agente || ''
      const clave = k.replace('.py', '')
      m[clave] = m[clave] || { veces: 0, ms: 0, fallos: 0 }
      m[clave].veces += 1
      m[clave].ms += ev.ms || 0
      if (ev.ok === false) m[clave].fallos += 1
    }
    return m
  }, [traza])

  if (error) {
    return (
      <section className="bloque aviso mal">
        <p>{error}</p>
        <div className="error">
          <strong>como</strong> Para el servidor y volve a levantarlo:
          <em>python harness/server.py</em>
        </div>
      </section>
    )
  }

  if (!flujo) return <section className="bloque"><p className="ayuda">Cargando el flujo…</p></section>

  return (
    <>
      <section className="bloque">
        <div className="bloque-cabecera">
          <div>
            <h2>El flujo de trabajo</h2>
            <p className="ayuda">
              Quien trabaja, en que orden, con que herramientas y contra que
              regla. Sale de <code>harness/flujo.yaml</code>, no de esta
              pantalla: asi no puede contar una historia distinta de la que corre.
            </p>
          </div>
          <select value={slug} onChange={(e) => setSlug(e.target.value)} style={{ maxWidth: 260 }}>
            <option value="">Comparar con un libro…</option>
            {libros.map((l) => (
              <option key={l.slug} value={l.slug}>{l.titulo}</option>
            ))}
          </select>
        </div>

        {flujo.fases.map((fase) => (
          <div key={fase.id} className="fase">
            <div className="fase-cabecera">
              <h3>{fase.titulo}</h3>
              <span>{fase.subtitulo}</span>
            </div>
            <ol className="pasos-flujo">
              {fase.pasos.map((p, i) => (
                <PasoFlujo key={i} paso={p} corrida={corridas[(p.agente || '').replace('.py', '')]} hayTraza={!!slug} />
              ))}
            </ol>
          </div>
        ))}
      </section>

      {slug && <Ejecucion eventos={traza.eventos} slug={slug} />}
    </>
  )
}

function PasoFlujo({ paso, corrida, hayTraza }) {
  const esScript = paso.tipo === 'script'
  return (
    <li className={`paso-flujo ${paso.tipo} ${paso.puerta ? 'es-puerta' : ''}`}>
      <div className="pf-marca">
        {paso.puerta ? <span className="pf-puerta">{paso.puerta}</span>
          : <span className={`pf-tipo ${paso.tipo}`}>{esScript ? 'script' : 'modelo'}</span>}
      </div>

      <div className="pf-cuerpo">
        <div className="pf-titulo">
          <code>{paso.agente}</code>
          {paso.opcional && <span className="pf-chip">opcional</span>}
          {paso.solo_si && <span className="pf-chip">solo si {paso.solo_si}</span>}
          {hayTraza && (
            corrida
              ? <span className={`pf-corrida ${corrida.fallos ? 'con-fallo' : ''}`}>
                  corrio {corrida.veces}× · {(corrida.ms / 1000).toFixed(0)}s
                  {corrida.fallos ? ` · ${corrida.fallos} fallo${corrida.fallos > 1 ? 's' : ''}` : ''}
                </span>
              : <span className="pf-corrida sin">no corrio</span>
          )}
        </div>

        <p className="pf-que">{paso.que}</p>

        <div className="pf-detalles">
          {paso.skill && <Detalle k="skill" v={paso.skill} />}
          {paso.herramientas?.length > 0 && <Detalle k="herramientas" v={paso.herramientas.join(', ')} />}
          {paso.herramientas?.length === 0 && paso.tipo === 'modelo' && (
            <Detalle k="herramientas" v="ninguna: devuelve texto y escribe el script" />
          )}
          {paso.reglas?.length > 0 && <Detalle k="comprueba" v={paso.reglas.join(' · ')} />}
          {paso.lee?.length > 0 && <Detalle k="lee" v={paso.lee.join(' · ')} />}
          {paso.escribe?.length > 0 && <Detalle k="escribe" v={paso.escribe.join(' · ')} />}
          {paso.si_falla && <Detalle k="si falla" v={paso.si_falla} alerta />}
        </div>

        {paso.nota && <p className="pf-nota">{paso.nota}</p>}
      </div>
    </li>
  )
}

function Detalle({ k, v, alerta }) {
  return (
    <div className={`pf-detalle ${alerta ? 'alerta' : ''}`}>
      <span className="pf-k">{k}</span>
      <span className="pf-v">{v}</span>
    </div>
  )
}

/** Lo que realmente se ejecuto, en orden, con el comando exacto. */
function Ejecucion({ eventos, slug }) {
  if (!eventos.length) {
    return (
      <section className="bloque">
        <h2>Lo que se ejecuto</h2>
        <p className="ayuda">
          <code>books/{slug}</code> todavia no corrio el ciclo, asi que no hay
          nada que comparar.
        </p>
      </section>
    )
  }

  return (
    <section className="bloque">
      <div className="bloque-cabecera">
        <div>
          <h2>Lo que se ejecuto</h2>
          <p className="ayuda">
            En orden, con el comando exacto. Esto es la traza real de{' '}
            <code>books/{slug}</code>, no el diagrama.
          </p>
        </div>
      </div>
      <ol className="ejecucion">
        {eventos.map((ev, i) => (
          <li key={i} className={ev.ok === false ? 'fallo' : ''}>
            <span className="ej-n">{String(i + 1).padStart(2, '0')}</span>
            <div className="ej-cuerpo">
              <div className="ej-linea">
                <code className="ej-agente">{ev.agente}</code>
                {ev.escena && <span className="ej-escena">{ev.escena} · intento {ev.intento}</span>}
                <span className="ej-ms">{((ev.ms || 0) / 1000).toFixed(1)}s</span>
              </div>
              {ev.comando && <code className="ej-comando">{ev.comando}</code>}
              <div className="ej-meta">
                {ev.skill && <span>skill <b>{ev.skill}</b></span>}
                {ev.herramientas?.length > 0 && <span>herramientas <b>{ev.herramientas.join(', ')}</b></span>}
                {ev.reglas?.length > 0 && <span>comprueba <b>{ev.reglas.join(', ')}</b></span>}
                {ev.tokens && <span>tokens <b>{ev.tokens.salida} out</b></span>}
                {ev.costo ? <span>costo <b>${ev.costo.toFixed(3)}</b></span> : null}
                {ev.prompt_chars ? <span>prompt <b>{(ev.prompt_chars / 1000).toFixed(1)}k chars</b></span> : null}
              </div>
              {(ev.errores || []).map((e, j) => (
                <div key={j} className="ej-error">
                  <strong>{e.regla}</strong> {e.mensaje}
                  {e.arreglo && <em>{e.arreglo}</em>}
                </div>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
