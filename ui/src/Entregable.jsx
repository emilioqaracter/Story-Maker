import { useMemo, useState } from 'react'

/**
 * El entregable se lee, no se inspecciona. Por eso va en columna angosta, con
 * serifa y sin el ruido del markdown: novela.md ya es el libro, y mostrarlo
 * como un volcado de archivo hacia parecer que faltaba un paso.
 */
export default function Entregable({ texto, slug }) {
  const [copiado, setCopiado] = useState(false)
  const doc = useMemo(() => parsear(texto), [texto])

  if (!texto.trim()) return null

  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1800)
    } catch {
      setCopiado(false)
    }
  }

  function descargar() {
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/markdown' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${slug}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="entregable">
      <div className="entregable-cabecera">
        <div>
          <h4>El entregable</h4>
          <p className="meta">
            {doc.palabras.toLocaleString('es')} palabras · {doc.capitulos.length} capitulo
            {doc.capitulos.length === 1 ? '' : 's'} · manuscript/novela.md
          </p>
        </div>
        <div className="acciones">
          <button type="button" onClick={copiar}>{copiado ? 'Copiado' : 'Copiar'}</button>
          <button type="button" onClick={descargar}>Descargar .md</button>
        </div>
      </div>

      <article className="lectura">
        {doc.titulo && <h1>{doc.titulo}</h1>}
        {doc.capitulos.map((cap, i) => (
          <section key={i}>
            {cap.titulo && <h2>{cap.titulo}</h2>}
            {cap.parrafos.map((p, j) => (
              <p key={j}>{p}</p>
            ))}
          </section>
        ))}
      </article>
    </div>
  )
}

/** novela.md es markdown muy chico: un titulo, capitulos y parrafos. */
function parsear(texto) {
  const lineas = texto.replace(/\r\n/g, '\n').split('\n')
  const doc = { titulo: '', capitulos: [], palabras: 0 }
  let cap = null
  let buffer = []

  const cerrarParrafo = () => {
    if (buffer.length) {
      if (!cap) cap = { titulo: '', parrafos: [] }
      // Dentro de un parrafo, los saltos de linea son forma, no separacion.
      cap.parrafos.push(buffer.join(' '))
      buffer = []
    }
  }
  const cerrarCapitulo = () => {
    cerrarParrafo()
    if (cap) doc.capitulos.push(cap)
    cap = null
  }

  for (const linea of lineas) {
    const l = linea.trim()
    if (l.startsWith('## ')) {
      cerrarCapitulo()
      cap = { titulo: l.slice(3), parrafos: [] }
    } else if (l.startsWith('# ')) {
      cerrarCapitulo()
      doc.titulo = l.slice(2)
    } else if (!l) {
      cerrarParrafo()
    } else {
      buffer.push(l)
      doc.palabras += l.split(/\s+/).filter(Boolean).length
    }
  }
  cerrarCapitulo()
  return doc
}
