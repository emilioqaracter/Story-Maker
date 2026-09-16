const NIVELES = ['amateur', 'profesional', 'seleccion', 'juvenil']

export default function Pedido({ slug, setSlug, respuestas, setRespuestas, epoca, setEpoca }) {
  const r = respuestas

  const set = (clave, valor) => setRespuestas({ ...r, [clave]: valor })
  const setAnidado = (clave, sub, valor) =>
    setRespuestas({ ...r, [clave]: { ...r[clave], [sub]: valor } })
  const setHilo = (i, valor) => {
    const hilos = [...r.hilos]
    hilos[i] = valor
    set('hilos', hilos)
  }

  function anio(valor) {
    // Un ano suelto se expande al ano entero: una sola epoca para todo el libro.
    if (/^\d{4}$/.test(valor)) {
      set('epoca', { desde: `${valor}-01-01`, hasta: `${valor}-12-31` })
    }
  }

  return (
    <section className="bloque">
      <h2>1 · Que novela queres</h2>
      <p className="ayuda">
        Solo se pregunta lo que solo vos podes decidir. Las fechas de nacimiento
        no son un capricho: la edad no se guarda, se calcula a la fecha de cada
        escena.
      </p>

      <div className="campos">
        <label className="ancho">
          <span className="etiqueta">Nombre de la carpeta</span>
          <input
            value={slug}
            placeholder="irene-2015"
            onChange={(e) => setSlug(e.target.value)}
          />
          <span className="nota">books/…, sin espacios</span>
        </label>

        <label>
          <span className="etiqueta">Deporte</span>
          <input value={r.deporte} placeholder="basquetbol" onChange={(e) => set('deporte', e.target.value)} />
        </label>

        <label>
          <span className="etiqueta">Ano</span>
          <input
            placeholder="1998"
            defaultValue={r.epoca.desde ? r.epoca.desde.slice(0, 4) : ''}
            onChange={(e) => anio(e.target.value)}
          />
          <span className="nota">
            {r.epoca.desde ? `${r.epoca.desde} → ${r.epoca.hasta}` : 'una sola epoca para todo el libro'}
          </span>
        </label>

        <label>
          <span className="etiqueta">Lugar</span>
          <input value={r.lugar} placeholder="Montevideo, Uruguay" onChange={(e) => set('lugar', e.target.value)} />
        </label>

        <label>
          <span className="etiqueta">Nivel</span>
          <select value={r.nivel} onChange={(e) => set('nivel', e.target.value)}>
            {NIVELES.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
      </div>

      <h3 className="sub">La pareja</h3>
      <div className="campos">
        {[['persona_a', 'Primera persona'], ['persona_b', 'Segunda persona']].map(([clave, titulo]) => (
          <fieldset key={clave}>
            <legend>{titulo}</legend>
            <label>
              <span className="etiqueta">Nombre y apellido</span>
              <input value={r[clave].nombre} onChange={(e) => setAnidado(clave, 'nombre', e.target.value)} />
            </label>
            <label>
              <span className="etiqueta">Fecha de nacimiento</span>
              <input type="date" value={r[clave].nacimiento} onChange={(e) => setAnidado(clave, 'nacimiento', e.target.value)} />
              <span className="nota">de aca sale la edad en cada escena</span>
            </label>
            <label>
              <span className="etiqueta">Que hace en ese mundo</span>
              <input value={r[clave].rol} onChange={(e) => setAnidado(clave, 'rol', e.target.value)} />
            </label>
          </fieldset>
        ))}
      </div>

      <h3 className="sub">Lo que los une y lo que los separa</h3>
      <div className="campos">
        <label className="ancho">
          <span className="etiqueta">Como se cruzan por primera vez</span>
          <input value={r.encuentro} onChange={(e) => set('encuentro', e.target.value)} />
        </label>

        <label className="ancho destacado">
          <span className="etiqueta">Que los separa</span>
          <textarea rows="2" value={r.obstaculo} onChange={(e) => set('obstaculo', e.target.value)} />
          <span className="nota">
            Sin obstaculo no hay romance, hay dos personas simpaticas. Lo mejor es
            algo donde lo que le conviene a uno le cuesta al otro.
          </span>
        </label>

        <label>
          <span className="etiqueta">Que pierde {r.persona_a.nombre.split(' ')[0] || 'la primera'}</span>
          <input value={r.precio.a} onChange={(e) => setAnidado('precio', 'a', e.target.value)} />
        </label>
        <label>
          <span className="etiqueta">Que pierde {r.persona_b.nombre.split(' ')[0] || 'la segunda'}</span>
          <input value={r.precio.b} onChange={(e) => setAnidado('precio', 'b', e.target.value)} />
          <span className="nota">de estos dos sale la pregunta dramatica</span>
        </label>
      </div>

      <h3 className="sub">La epoca</h3>
      <p className="ayuda">
        Sin esto G0 no abre, y con razon: si la lista esta vacia, V8 no tiene
        nada que vetar y la epoca es decorativa. Un agente podria investigarla,
        pero es el paso mas lento del arranque y aca se escribe a mano.
      </p>
      <div className="campos">
        <label className="ancho destacado">
          <span className="etiqueta">Que NO existia todavia</span>
          <textarea
            rows="4"
            value={epoca.prohibido}
            placeholder={['celular', 'internet', 'VAR'].join('\n')}
            onChange={(e) => setEpoca({ ...epoca, prohibido: e.target.value })}
          />
          <span className="nota">
            uno por linea. Son las palabras que el validador veta en la prosa (V8).
          </span>
        </label>
        <label className="ancho">
          <span className="etiqueta">Como era</span>
          <textarea
            rows="2"
            value={epoca.notas}
            onChange={(e) => setEpoca({ ...epoca, notas: e.target.value })}
          />
          <span className="nota">como se seguia un partido, como era la vida cotidiana</span>
        </label>
        <label className="ancho">
          <span className="etiqueta">Fuentes</span>
          <textarea
            rows="2"
            value={epoca.fuentes}
            onChange={(e) => setEpoca({ ...epoca, fuentes: e.target.value })}
          />
          <span className="nota">
            una por linea. Lo que no trae fuente no entra en el canon.
          </span>
        </label>
      </div>

      <h3 className="sub">Lo demas que esta en juego</h3>
      <div className="campos">
        <label>
          <span className="etiqueta">Hilo 1</span>
          <input value={r.hilos[0]} onChange={(e) => setHilo(0, e.target.value)} />
        </label>
        <label>
          <span className="etiqueta">Hilo 2</span>
          <input value={r.hilos[1]} onChange={(e) => setHilo(1, e.target.value)} />
          <span className="nota">exactamente dos: su numero no crece durante la escritura</span>
        </label>
      </div>
    </section>
  )
}
