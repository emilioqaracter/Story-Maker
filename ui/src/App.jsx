import { useEffect, useMemo, useState } from 'react'
import Pedido, { EJEMPLO } from './Pedido.jsx'
import Configuracion from './Configuracion.jsx'
import Libros from './Libros.jsx'
import { api, derivar } from './api.js'

const RESPUESTAS_VACIAS = {
  deporte: '',
  epoca: { desde: '', hasta: '' },
  lugar: '',
  nivel: 'profesional',
  persona_a: { nombre: '', nacimiento: '', rol: '' },
  persona_b: { nombre: '', nacimiento: '', rol: '' },
  encuentro: '',
  obstaculo: '',
  precio: { a: '', b: '' },
  hilos: ['', ''],
}

export default function App() {
  const [config, setConfig] = useState(null)
  const [estructura, setEstructura] = useState(null)
  const [respuestas, setRespuestas] = useState(RESPUESTAS_VACIAS)
  const [slug, setSlug] = useState('')
  const [epoca, setEpoca] = useState({ prohibido: '', notas: '', fuentes: '' })
  const [libros, setLibros] = useState([])
  const [aviso, setAviso] = useState(null)

  useEffect(() => {
    api.config().then((c) => {
      setConfig(c)
      setEstructura(c.estructura)
    })
    refrescar()
  }, [])

  function refrescar() {
    api.libros().then(setLibros).catch(() => {})
  }

  // Las mismas cuentas que hace el harness, en vivo mientras se escribe.
  // Nada de esto se guarda: se deriva de los cinco numeros de arriba.
  const forma = useMemo(
    () => (estructura && config ? derivar(estructura, config.tolerancia) : null),
    [estructura, config],
  )

  const faltan = useMemo(() => camposQueFaltan(slug, respuestas, epoca), [slug, respuestas, epoca])

  async function crear() {
    setAviso(null)
    const lineas = (t) => t.split(/\r?\n/).map((x) => x.trim()).filter(Boolean)
    const r = await api.crear({
      slug,
      estructura,
      respuestas,
      prohibido: lineas(epoca.prohibido),
      notas_epoca: epoca.notas.trim(),
      fuentes: lineas(epoca.fuentes),
    })
    if (!r.ok) return setAviso({ tipo: 'mal', texto: r.error || 'No se pudo crear.' })
    const g0 = r.g0 || {}
    setAviso({
      tipo: g0.ok ? 'bien' : 'aviso',
      texto: g0.ok
        ? `Creado books/${r.slug}. G0 abre: el canon esta completo.`
        : `Creado books/${r.slug}, pero G0 no abre todavia.`,
      errores: g0.errores || [],
    })
    refrescar()
  }

  if (!config || !estructura) return <div className="cargando">Conectando con el harness…</div>

  return (
    <div className="pagina">
      <header>
        <p className="kicker">Harness de novelas</p>
        <h1>Story-Maker</h1>
        <p className="bajada">
          Lo que escribas abajo es el canon. A partir de ahi el modelo escribe y
          el codigo verifica: cinco puertas deciden que entra y que se rehace.
        </p>
      </header>

      <Pedido
        slug={slug}
        setSlug={setSlug}
        respuestas={respuestas}
        setRespuestas={setRespuestas}
        epoca={epoca}
        setEpoca={setEpoca}
        cargarEjemplo={() => {
          setSlug(EJEMPLO.slug)
          setRespuestas(structuredClone(EJEMPLO.respuestas))
          setEpoca({ ...EJEMPLO.epoca })
        }}
      />

      <Configuracion
        config={config}
        estructura={estructura}
        setEstructura={setEstructura}
        forma={forma}
      />

      <section className="bloque accion">
        <div>
          {faltan.length > 0 ? (
            <p className="falta">
              Faltan {faltan.length}: <span>{faltan.join(' · ')}</span>
            </p>
          ) : (
            <p className="listo">Todo completo. Se crean {forma.escenas_totales} escenas planificadas.</p>
          )}
        </div>
        <button className="primario" disabled={faltan.length > 0} onClick={crear}>
          Crear el canon
        </button>
      </section>

      {aviso && (
        <section className={`bloque aviso ${aviso.tipo}`}>
          <p>{aviso.texto}</p>
          {(aviso.errores || []).map((e, i) => (
            <div key={i} className="error">
              <strong>{e.regla}</strong> {e.mensaje}
              <em>{e.arreglo}</em>
            </div>
          ))}
        </section>
      )}

      <Libros libros={libros} refrescar={refrescar} />

      <footer>
        <p>
          La UI no decide nada: crea el canon y lanza los mismos scripts que
          corren en la terminal. Las puertas siguen siendo de ellos.
        </p>
      </footer>
    </div>
  )
}

function camposQueFaltan(slug, r, epoca) {
  const falta = []
  if (!slug.trim()) falta.push('carpeta')
  if (!r.deporte.trim()) falta.push('deporte')
  if (!r.epoca.desde || !r.epoca.hasta) falta.push('epoca')
  if (!r.lugar.trim()) falta.push('lugar')
  for (const [clave, etiqueta] of [['persona_a', 'primera persona'], ['persona_b', 'segunda persona']]) {
    const p = r[clave]
    if (!p.nombre.trim() || !p.nacimiento || !p.rol.trim()) falta.push(etiqueta)
  }
  if (!r.encuentro.trim()) falta.push('encuentro')
  if (!r.obstaculo.trim()) falta.push('obstaculo')
  if (!r.precio.a.trim() || !r.precio.b.trim()) falta.push('precio')
  if (!r.hilos[0].trim() || !r.hilos[1].trim()) falta.push('hilos')
  // Sin anacronismos G0 no abre: mejor decirlo aca que despues de crear.
  if (!epoca.prohibido.trim()) falta.push('anacronismos')
  if (!epoca.fuentes.trim()) falta.push('fuentes')
  return falta
}
