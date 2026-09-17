import { useEffect, useState } from 'react'
import { api } from './api.js'
import Entregable from './Entregable.jsx'
import Traza from './Traza.jsx'

export default function Libros({ libros, refrescar }) {
  const [abierto, setAbierto] = useState(null)

  const cabecera = (
    <div className="bloque-cabecera">
      <div>
        <span className="paso">3</span>
        <h2>Los libros</h2>
        <p className="ayuda">
          {libros.length
            ? 'El ciclo escribe, valida, critica y corrige cada escena. Aca se ve en que orden trabajo cada agente, cuanto tardo y donde se trabo.'
            : 'Todavia no hay ninguno. Llena el pedido de arriba.'}
        </p>
      </div>
    </div>
  )

  return (
    <section className="bloque">
      {cabecera}
      {libros.length > 0 && (
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
      )}
    </section>
  )
}

const PESTANAS = [
  ['traza', 'Como funciono'],
  ['escenas', 'Escenas'],
  ['entregable', 'El texto'],
  ['log', 'Log crudo'],
]

function Libro({ libro, abierto, alternar, refrescar }) {
  const [log, setLog] = useState('')
  const [corriendo, setCorriendo] = useState(libro.corriendo)
  const [novela, setNovela] = useState('')
  const [traza, setTraza] = useState({ eventos: [], resumen: null })
  const [pestana, setPestana] = useState('traza')

  // Mientras corre, el ciclo tarda minutos: se consulta en vez de bloquear.
  // El estado real siempre esta en disco, asi que refrescar no puede mentir.
  useEffect(() => {
    if (!corriendo && !abierto) return
    const t = setInterval(async () => {
      const r = await api.log(libro.slug)
      setLog(r.log)
      api.traza(libro.slug).then(setTraza)
      if (!r.corriendo && corriendo) {
        setCorriendo(false)
        refrescar()
        api.novela(libro.slug).then((n) => setNovela(n.texto))
      }
    }, 2000)
    return () => clearInterval(t)
  }, [corriendo, abierto, libro.slug])

  useEffect(() => {
    if (!abierto) return
    api.novela(libro.slug).then((n) => setNovela(n.texto))
    api.traza(libro.slug).then(setTraza)
  }, [abierto, libro.slug, libro.aprobadas])

  // Un solo conductor: Claude Code siguiendo la skill `dirigir-novela`. El
  // bucle en Python se quito del repo en la v9.0.
  async function correr() {
    const r = await api.correr(libro.slug)
    if (r.ok) {
      setCorriendo(true)
      setPestana('traza')
    } else if (r.error) {
      setLog(r.error)
      setPestana('log')
    }
  }

  async function reiniciar() {
    await api.reset(libro.slug)
    setNovela('')
    setLog('')
    setTraza({ eventos: [], resumen: null })
    refrescar()
  }

  const total = libro.escenas.length
  const pct = total ? Math.round((libro.aprobadas / total) * 100) : 0
  const cerradas = traza.resumen?.puertas_cerradas || 0

  return (
    <article className={`libro ${corriendo ? 'activo' : ''}`}>
      <header onClick={alternar}>
        <div>
          <h3>{libro.titulo}</h3>
          <p className="meta">
            {libro.deporte} · {libro.epoca?.desde?.slice(0, 4)} · {total} escenas
            {corriendo && <span className="latido"> corriendo</span>}
          </p>
        </div>
        <div className="progreso">
          <div className="barra">
            <span style={{ width: `${pct}%` }} />
          </div>
          <p className="meta">
            {libro.aprobadas}/{total} aprobadas · {libro.palabras_escritas}/
            {libro.forma.techo_palabras} palabras
          </p>
        </div>
      </header>

      {abierto && (
        <div className="detalle">
          <div className="acciones">
            <button className="primario" onClick={correr} disabled={corriendo}>
              {corriendo ? 'Corriendo…' : 'Escribir con Claude Code'}
            </button>
            <button onClick={reiniciar} disabled={corriendo}>Reset</button>
            <span className="nota">
              Claude Code conduce el ciclo entero. Reset borra prosa, criticas,
              traza y estado — el canon no se toca.
            </span>
          </div>

          <nav className="pestanas">
            {PESTANAS.map(([id, texto]) => (
              <button
                key={id}
                type="button"
                className={pestana === id ? 'activa' : ''}
                onClick={() => setPestana(id)}
              >
                {texto}
                {id === 'traza' && cerradas > 0 && <span className="globo">{cerradas}</span>}
              </button>
            ))}
          </nav>

          {pestana === 'traza' &&
            (traza.resumen ? (
              <Traza eventos={traza.eventos} resumen={traza.resumen} />
            ) : (
              <p className="ayuda">Todavia no hay traza. Se escribe sola al correr el ciclo.</p>
            ))}

          {pestana === 'escenas' && (
            <table>
              <thead>
                <tr>
                  <th>Escena</th>
                  <th>Cap</th>
                  <th>Fecha</th>
                  <th>Estado</th>
                  <th>Cierra</th>
                  <th>Palabras</th>
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
          )}

          {pestana === 'entregable' &&
            (novela ? (
              <Entregable texto={novela} slug={libro.slug} />
            ) : (
              <p className="ayuda">Todavia no hay entregable: se compila al abrir G4.</p>
            ))}

          {pestana === 'log' &&
            (log ? (
              <pre className="log">{log.split('\n').slice(-40).join('\n')}</pre>
            ) : (
              <p className="ayuda">Sin log todavia.</p>
            ))}
        </div>
      )}
    </article>
  )
}
