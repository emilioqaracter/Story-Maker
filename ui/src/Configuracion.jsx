const CAMPOS = [
  ['capitulos', 'Capitulos', 'cuantas veces paras a leer (G3)'],
  ['escenas_por_capitulo', 'Escenas por capitulo', 'cada una es una vuelta del ciclo'],
  ['parrafos_por_escena', 'Parrafos por escena', 'lo comprueba V14, exacto'],
  ['lineas_por_parrafo', 'Lineas por parrafo', 'lo comprueba V15, exacto'],
  ['palabras_por_linea', 'Palabras por linea', 'objetivo; V15 tolera un margen'],
]

export default function Configuracion({ config, estructura, setEstructura, forma }) {
  const tol = config.tolerancia.palabras_por_linea

  function aplicarPerfil(nombre) {
    setEstructura({ ...config.perfiles[nombre] })
  }

  function cambiar(clave, valor) {
    const n = Math.max(1, parseInt(valor || '1', 10))
    setEstructura({ ...estructura, [clave]: n })
  }

  return (
    <section className="bloque">
      <h2>2 · La forma del documento</h2>
      <p className="ayuda">
        De estos cinco numeros sale todo lo demas. Las cifras de la derecha no se
        guardan en ningun lado: se calculan.
      </p>

      <div className="perfiles">
        <span>Perfiles:</span>
        {Object.keys(config.perfiles).map((p) => (
          <button key={p} className="chip" onClick={() => aplicarPerfil(p)}>
            {p}
          </button>
        ))}
      </div>

      <div className="config">
        <div className="numeros">
          {CAMPOS.map(([clave, etiqueta, nota]) => (
            <label key={clave}>
              <span className="etiqueta">{etiqueta}</span>
              <input
                type="number"
                min="1"
                value={estructura[clave]}
                onChange={(e) => cambiar(clave, e.target.value)}
              />
              <span className="nota">{nota}</span>
            </label>
          ))}
        </div>

        <div className="derivado">
          <h3>Se deriva</h3>
          <dl>
            <div>
              <dt>Lineas por escena</dt>
              <dd>{forma.lineas_por_escena}</dd>
            </div>
            <div>
              <dt>Palabras por escena</dt>
              <dd>
                {forma.palabras_por_escena}
                <small> objetivo</small>
              </dd>
            </div>
            <div>
              <dt>Maximo que V15 tolera</dt>
              <dd>
                {forma.palabras_por_escena_max}
                <small> {estructura.palabras_por_linea}±{tol} por linea</small>
              </dd>
            </div>
            <div>
              <dt>Escenas en total</dt>
              <dd>{forma.escenas_totales}</dd>
            </div>
            <div className="destacado">
              <dt>El libro</dt>
              <dd>~{forma.palabras_libro.toLocaleString('es')} palabras</dd>
            </div>
            <div className="destacado">
              <dt>Techo</dt>
              <dd>
                {forma.techo_palabras.toLocaleString('es')}
                <small> presupuesta el maximo</small>
              </dd>
            </div>
          </dl>
          <p className="ayuda chica">
            El techo se calcula con la escena mas larga que V15 deja pasar, no con
            la nominal. Si no, un libro pasaria todas las reglas de escena y
            reventaria el techo igual.
          </p>
        </div>
      </div>
    </section>
  )
}
