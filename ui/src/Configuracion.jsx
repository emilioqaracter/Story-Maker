const CAMPOS = [
  ['capitulos', 'Capitulos', 'cada uno es una parada para leer (G3)', '2'],
  ['escenas_por_capitulo', 'Escenas por capitulo', 'cada una es una vuelta del ciclo', '2'],
  ['parrafos_por_escena', 'Parrafos por escena', 'exacto, lo comprueba V14', '5'],
  ['lineas_por_parrafo', 'Lineas por parrafo', 'exacto, lo comprueba V15', '5'],
  ['palabras_por_linea', 'Palabras por linea', 'objetivo; V15 tolera un margen', '12'],
]

const mismos = (a, b) => CAMPOS.every(([k]) => a[k] === b[k])

export default function Configuracion({ config, estructura, setEstructura, forma }) {
  const tol = config.tolerancia.palabras_por_linea
  // Cual perfil esta puesto. Si no coincide con ninguno, es personalizado: sin
  // esto no habia forma de saber cual estaba activo ni de ver que el clic tomo.
  const activo =
    Object.keys(config.perfiles).find((p) => mismos(config.perfiles[p], estructura)) || null

  const cambiar = (clave, valor) =>
    setEstructura({ ...estructura, [clave]: Math.max(1, parseInt(valor || '1', 10)) })

  return (
    <section className="bloque">
      <div className="bloque-cabecera">
        <div>
          <span className="paso">2</span>
          <h2>La forma del documento</h2>
          <p className="ayuda">
            De estos cinco numeros sale todo lo demas. Lo de la derecha no se
            guarda en ningun archivo: se calcula.
          </p>
        </div>
      </div>

      <div className="segmentado" role="group" aria-label="Perfil">
        {Object.keys(config.perfiles).map((p) => (
          <button
            key={p}
            type="button"
            className={activo === p ? 'activo' : ''}
            aria-pressed={activo === p}
            onClick={() => setEstructura({ ...config.perfiles[p] })}
          >
            <strong>{p}</strong>
            <small>{resumen(config.perfiles[p])}</small>
          </button>
        ))}
        <span className={`personalizado ${activo ? '' : 'puesto'}`}>
          {activo ? '' : 'personalizado'}
        </span>
      </div>

      <div className="config">
        <div className="numeros">
          {CAMPOS.map(([clave, etiqueta, nota, ej]) => (
            <label key={clave} className="campo numero">
              <span className="etiqueta">{etiqueta}</span>
              <input
                type="number"
                min="1"
                value={estructura[clave]}
                onChange={(e) => cambiar(clave, e.target.value)}
              />
              <span className="ejemplo">
                <span className="ej">ej</span>
                {ej}
              </span>
              <span className="nota">{nota}</span>
            </label>
          ))}
        </div>

        <div className="derivado">
          <h3>Se deriva</h3>
          <dl>
            <Fila dt="Lineas por escena" dd={forma.lineas_por_escena} />
            <Fila dt="Palabras por escena" dd={forma.palabras_por_escena} pie="objetivo" />
            <Fila
              dt="Maximo que V15 tolera"
              dd={forma.palabras_por_escena_max}
              pie={`${estructura.palabras_por_linea}±${tol} por linea`}
            />
            <Fila dt="Escenas en total" dd={forma.escenas_totales} />
            <div className="separador" />
            <Fila destacado dt="El libro" dd={`~${forma.palabras_libro.toLocaleString('es')}`} pie="palabras" />
            <Fila destacado dt="Techo" dd={forma.techo_palabras.toLocaleString('es')} pie="no se puede pasar" />
          </dl>
          <p className="ayuda chica">
            El techo se presupuesta con la escena mas larga que V15 deja pasar,
            no con la nominal. Si no, un libro pasaria todas las reglas de escena
            y reventaria el techo igual.
          </p>
        </div>
      </div>
    </section>
  )
}

function Fila({ dt, dd, pie, destacado }) {
  return (
    <div className={destacado ? 'destacado' : ''}>
      <dt>{dt}</dt>
      <dd>
        {dd}
        {pie && <small>{pie}</small>}
      </dd>
    </div>
  )
}

function resumen(p) {
  const escenas = p.capitulos * p.escenas_por_capitulo
  const palabras = p.parrafos_por_escena * p.lineas_por_parrafo * p.palabras_por_linea * escenas
  return `${escenas} esc · ${palabras.toLocaleString('es')} pal`
}
