import { useMemo, useState } from 'react'

/**
 * Como funciona el sistema por detras: el orden real de los pasos, cuanto
 * tardo cada agente, cuantos tokens gasto, y —lo que mas importa— que dijo
 * cada puerta cuando cerro. Un intento fallido sin su motivo no ensena nada.
 */
export default function Traza({ eventos, resumen }) {
  const grupos = useMemo(() => agrupar(eventos), [eventos])

  if (!eventos.length) {
    return (
      <p className="ayuda" style={{ marginTop: 16 }}>
        Todavia no hay traza. Se escribe sola en cuanto corras el ciclo.
      </p>
    )
  }

  return (
    <div className="traza">
      <div className="totales">
        <Total valor={seg(resumen.ms_total)} etiqueta="tiempo total" />
        <Total valor={seg(resumen.ms_modelo)} etiqueta="en el modelo" />
        <Total valor={resumen.llamadas} etiqueta="llamadas" />
        <Total valor={mil(resumen.salida)} etiqueta="tokens escritos" />
        <Total valor={mil(resumen.entrada + resumen.cache_escrita + resumen.cache_leida)} etiqueta="tokens leidos" />
        <Total valor={`$${resumen.costo.toFixed(2)}`} etiqueta="costo" />
        <Total valor={resumen.reintentos} etiqueta="reintentos" alerta={resumen.reintentos > 0} />
        <Total valor={resumen.puertas_cerradas} etiqueta="puertas cerradas" alerta={resumen.puertas_cerradas > 0} />
      </div>

      {Object.keys(resumen.por_agente).length > 0 && (
        <div className="por-agente">
          {Object.entries(resumen.por_agente)
            .sort((a, b) => b[1].ms - a[1].ms)
            .map(([nombre, a]) => (
              <div key={nombre} className="agente-fila">
                <span className="agente-nombre">{nombre}</span>
                <div className="agente-barra">
                  <span style={{ width: `${(a.ms / Math.max(1, resumen.ms_modelo)) * 100}%` }} />
                </div>
                <span className="agente-cifra">
                  {a.llamadas}× · {seg(a.ms)} · ${a.costo.toFixed(2)}
                </span>
              </div>
            ))}
        </div>
      )}

      <ol className="linea">
        {grupos.map((g, i) => (
          <Grupo key={i} grupo={g} />
        ))}
      </ol>
    </div>
  )
}

function Grupo({ grupo }) {
  const [abierto, setAbierto] = useState(grupo.fallo)
  const { titulo, eventos, fallo, ms } = grupo

  return (
    <li className={`grupo ${fallo ? 'fallo' : ''}`}>
      <button type="button" className="grupo-cabecera" onClick={() => setAbierto(!abierto)}>
        <span className={`punto ${fallo ? 'malo' : 'bueno'}`} />
        <span className="grupo-titulo">{titulo}</span>
        <span className="grupo-meta">
          {eventos.length} paso{eventos.length === 1 ? '' : 's'} · {seg(ms)}
        </span>
      </button>

      {abierto && (
        <ol className="pasos">
          {eventos.map((e, i) => (
            <Paso key={i} ev={e} />
          ))}
        </ol>
      )}
    </li>
  )
}

function Paso({ ev }) {
  const errores = ev.errores || []
  const esModelo = ev.tipo === 'modelo'
  const fallo = ev.ok === false

  return (
    <li className={`paso-traza ${ev.tipo} ${fallo ? 'fallo' : ''}`}>
      <div className="paso-linea">
        <span className={`etiqueta-tipo ${ev.tipo}`}>
          {ev.tipo === 'puerta' ? ev.paso : ev.tipo === 'modelo' ? 'modelo' : ev.paso}
        </span>
        <span className="paso-agente">{ev.agente}</span>
        <span className="paso-cifras">
          {seg(ev.ms)}
          {esModelo && ev.tokens && (
            <>
              {' · '}
              <abbr title="tokens escritos por el modelo">{mil(ev.tokens.salida)} out</abbr>
              {' · '}
              <abbr title="entrada + cache escrita + cache leida">
                {mil(ev.tokens.entrada + ev.tokens.cache_escrita + ev.tokens.cache_leida)} in
              </abbr>
            </>
          )}
          {esModelo && ev.costo ? ` · $${ev.costo.toFixed(3)}` : ''}
          {ev.palabras ? ` · ${ev.palabras} palabras` : ''}
          {ev.suma != null ? ` · rubrica ${ev.suma}/${ev.umbral * 2 >= 10 ? 10 : 8}` : ''}
        </span>
      </div>

      {ev.detalle && <p className="paso-detalle">{ev.detalle}</p>}

      {errores.length > 0 && (
        <ul className="paso-errores">
          {errores.map((e, i) => (
            <li key={i}>
              <strong>{e.regla}</strong>
              <span>{e.mensaje}</span>
              {e.arreglo && <em>{e.arreglo}</em>}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/** Agrupa por escena+intento: es la unidad en la que se piensa el ciclo. */
function agrupar(eventos) {
  const grupos = []
  let actual = null

  for (const ev of eventos) {
    const clave = ev.escena ? `${ev.escena}·${ev.intento || 1}` : ev.fase || 'otros'
    if (!actual || actual.clave !== clave) {
      actual = {
        clave,
        titulo: ev.escena ? `${ev.escena} · intento ${ev.intento || 1}` : tituloFase(ev.fase),
        eventos: [],
        ms: 0,
        fallo: false,
      }
      grupos.push(actual)
    }
    actual.eventos.push(ev)
    actual.ms += ev.ms || 0
    if (ev.ok === false) actual.fallo = true
  }
  return grupos
}

const tituloFase = (f) =>
  ({ arranque: 'Arranque · el canon', investigar: 'Investigar la epoca',
     planificar: 'Planificar las escenas', cierre: 'Cierre · G4 y compilado' }[f] || f || 'otros')

const seg = (ms) => (ms >= 60000 ? `${Math.round(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s` : `${(ms / 1000).toFixed(1)}s`)
const mil = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n || 0))

function Total({ valor, etiqueta, alerta }) {
  return (
    <div className={`total ${alerta ? 'alerta' : ''}`}>
      <span className="total-valor">{valor}</span>
      <span className="total-etiqueta">{etiqueta}</span>
    </div>
  )
}
