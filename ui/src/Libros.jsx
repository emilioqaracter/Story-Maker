import { useEffect, useState } from 'react'
import { api } from './api.js'

export default function Libros({ libros, refrescar }) {
  const [abierto, setAbierto] = useState(null)

  if (!libros.length) {
    return (
      <section className="bloque">
        <h2>3 · Los libros</h2>
        <p className="ayuda">Todavia no hay ninguno.</p>
      </section>
    )
  }

  return (
    <section className="bloque">
      <h2>3 · Los libros</h2>
      <div className="libros">
        {libros.map((l) => (
          <Libro
            key={l.slug}
            libro={l}
            abierto={abierto === l.slug}
            alternar={() => setAbierto(abierto === l.slug ? null : l.slug)}
            refrescar={refrescar}
          />
        ))}
      </div>
    </section>
  )
}

function Libro({ libro, abierto, alternar, refrescar }) {
  const [log, setLog] = useState('')
  const [corriendo, setCorriendo] = useState(libro.corriendo)
  const [novela, setNovela] = useState('')

  // Mientras corre, el ciclo tarda minutos: se consulta el log en vez de
  // bloquear. El estado real siempre esta en disco.
  useEffect(() => {
    if (!corriendo && !abierto) return
    const t = setInterval(async () => {
      const r = await api.log(libro.slug)
      setLog(r.log)
      if (!r.corriendo && corriendo) {
        setCorriendo(false)
        refrescar()
        api.novela(libro.slug).then((n) => setNovela(n.texto))
      }
    }, 2000)
    return () => clearInterval(t)
  }, [corriendo, abierto, libro.slug])

  useEffect(() => {
    if (abierto) api.novela(libro.slug).then((n) => setNovela(n.texto))
  }, [abierto, libro.slug, libro.aprobadas])

  async function correr() {
    const r = await api.correr(libro.slug)
    if (r.ok) setCorriendo(true)
  }

  async function reiniciar() {
    await api.reset(libro.slug)
    setNovela('')
    setLog('')
    refrescar()
  }

  const total = libro.escenas.length
  const pct = total ? Math.round((libro.aprobadas / total) * 100) : 0

  return (
    <article className={`libro ${corriendo ? 'activo' : ''}`}>
      <header onClick={alternar}>
        <div>
          <h3>{libro.titulo}</h3>
          <p className="meta">
            {libro.deporte} · {libro.epoca?.desde?.slice(0, 4)} · {total} escenas
          </p>
        </div>
        <div className="progreso">
          <div className="barra">
            <span style={{ width: `${pct}%` }} />
          </div>
          <p className="meta">
            {libro.aprobadas}/{total} aprobadas ·{' '}
            {libro.palabras_escritas}/{libro.forma.techo_palabras} palabras
          </p>
        </div>
      </header>

      {abierto && (
        <div className="detalle">
          <table>
            <thead>
              <tr>
                <th>Escena</th><th>Cap</th><th>Fecha</th><th>Estado</th><th>Cierra</th><th>Palabras</th>
              </tr>
            </thead>
            <tbody>
              {libro.escenas.map((e) => (
                <tr key={e.id} className={e.estado}>
                  <td>{e.id}</td>
                  <td>{e.capitulo}</td>
                  <td>{e.fecha}</td>
                  <td><span className={`pastilla ${e.estado}`}>{e.estado}</span></td>
                  <td>{e.cierra.join(' ') || '—'}</td>
                  <td>{e.palabras || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="acciones">
            <button className="primario" onClick={correr} disabled={corriendo}>
              {corriendo ? 'Corriendo…' : 'Correr el ciclo'}
            </button>
            <button onClick={reiniciar} disabled={corriendo}>Reset</button>
            <span className="nota">
              Reset borra prosa, criticas y estado. No toca el canon.
            </span>
          </div>

          {log && (
            <pre className="log">{log.split('\n').slice(-30).join('\n')}</pre>
          )}

          {novela && (
            <div className="novela">
              <h4>El entregable</h4>
              <pre>{novela}</pre>
            </div>
          )}
        </div>
      )}
    </article>
  )
}
