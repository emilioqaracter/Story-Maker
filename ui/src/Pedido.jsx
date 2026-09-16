import Campo from './Campo.jsx'

const NIVELES = ['amateur', 'profesional', 'seleccion', 'juvenil']

export const EJEMPLO = {
  slug: 'vera-1998',
  respuestas: {
    deporte: 'basquetbol',
    epoca: { desde: '1998-01-01', hasta: '1998-12-31' },
    lugar: 'Montevideo, Uruguay',
    nivel: 'seleccion',
    persona_a: { nombre: 'Vera Olmos', nacimiento: '1972-06-04', rol: 'base de la seleccion, la mas veterana del plantel' },
    persona_b: { nombre: 'Ruben Alcaide', nacimiento: '1968-01-30', rol: 'entrenador de la seleccion, primer ciclo a cargo' },
    encuentro: 'El la corta de la lista y se la cruza esa misma noche en el gimnasio vacio',
    obstaculo: 'Si el la convoca lo acusan de favoritismo; si no la convoca, ella se retira',
    precio: { a: 'el ultimo mundial que le queda', b: 'el puesto que le costo veinte anos' },
    hilos: ['la lista de doce que hay que cerrar', 'el gimnasio del barrio que van a demoler'],
  },
  epoca: {
    prohibido: 'celular con camara\nInstagram\nYouTube\nVAR\neuro',
    notas: 'Los partidos se seguian por radio; el resumen llegaba al dia siguiente en el diario.',
    fuentes: 'https://es.wikipedia.org/wiki/1998',
  },
}

export default function Pedido({ slug, setSlug, respuestas, setRespuestas, epoca, setEpoca, cargarEjemplo }) {
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
    if (/^\d{4}$/.test(valor)) set('epoca', { desde: `${valor}-01-01`, hasta: `${valor}-12-31` })
    else if (!valor.trim()) set('epoca', { desde: '', hasta: '' })
  }

  const nombreA = r.persona_a.nombre.split(' ')[0]
  const nombreB = r.persona_b.nombre.split(' ')[0]

  return (
    <section className="bloque">
      <div className="bloque-cabecera">
        <div>
          <span className="paso">1</span>
          <h2>Que novela queres</h2>
          <p className="ayuda">
            Solo se pregunta lo que solo vos podes decidir. Lo verificable y lo
            calculable no se preguntan.
          </p>
        </div>
        <button type="button" className="fantasma" onClick={cargarEjemplo}>
          Cargar un ejemplo
        </button>
      </div>

      <h3 className="sub">El mundo</h3>
      <div className="campos">
        <Campo
          etiqueta="Nombre de la carpeta"
          ejemplo="vera-1998"
          nota="va a books/…, sin espacios"
          valor={slug}
          onChange={setSlug}
        />
        <Campo
          etiqueta="Deporte"
          ejemplo="basquetbol · ciclismo · natacion · boxeo"
          valor={r.deporte}
          onChange={(v) => set('deporte', v)}
        />
        <Campo
          etiqueta="Ano"
          ejemplo="1998"
          nota={r.epoca.desde ? `${r.epoca.desde} → ${r.epoca.hasta}` : 'una sola epoca para todo el libro'}
        >
          <input
            defaultValue={r.epoca.desde ? r.epoca.desde.slice(0, 4) : ''}
            key={r.epoca.desde}
            onChange={(e) => anio(e.target.value)}
          />
        </Campo>
        <Campo
          etiqueta="Lugar"
          ejemplo="Montevideo, Uruguay"
          valor={r.lugar}
          onChange={(v) => set('lugar', v)}
        />
        <Campo etiqueta="Nivel" ejemplo="seleccion">
          <select value={r.nivel} onChange={(e) => set('nivel', e.target.value)}>
            {NIVELES.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </Campo>
      </div>

      <h3 className="sub">La pareja</h3>
      <div className="campos dos">
        {[
          ['persona_a', 'Primera persona', { nombre: 'Vera Olmos', rol: 'base de la seleccion, la mas veterana del plantel' }],
          ['persona_b', 'Segunda persona', { nombre: 'Ruben Alcaide', rol: 'entrenador de la seleccion, primer ciclo a cargo' }],
        ].map(([clave, titulo, ej]) => (
          <fieldset key={clave}>
            <legend>{titulo}</legend>
            <Campo
              etiqueta="Nombre y apellido"
              ejemplo={ej.nombre}
              valor={r[clave].nombre}
              onChange={(v) => setAnidado(clave, 'nombre', v)}
            />
            <Campo
              etiqueta="Fecha de nacimiento"
              tipo="date"
              nota="la edad no se guarda: se calcula a la fecha de cada escena"
              valor={r[clave].nacimiento}
              onChange={(v) => setAnidado(clave, 'nacimiento', v)}
            />
            <Campo
              etiqueta="Que hace en ese mundo"
              ejemplo={ej.rol}
              valor={r[clave].rol}
              onChange={(v) => setAnidado(clave, 'rol', v)}
            />
          </fieldset>
        ))}
      </div>

      <h3 className="sub">Lo que los une y lo que los separa</h3>
      <div className="campos">
        <Campo
          ancho
          etiqueta="Como se cruzan por primera vez"
          ejemplo="El la corta de la lista y se la cruza esa misma noche en el gimnasio vacio"
          valor={r.encuentro}
          onChange={(v) => set('encuentro', v)}
        />
        <Campo
          ancho
          destacado
          filas={2}
          etiqueta="Que los separa"
          ejemplo="Si el la convoca lo acusan de favoritismo; si no la convoca, ella se retira"
          nota="Sin obstaculo no hay romance, hay dos personas simpaticas. Lo mejor es algo donde lo que le conviene a uno le cuesta al otro."
          valor={r.obstaculo}
          onChange={(v) => set('obstaculo', v)}
        />
        <Campo
          etiqueta={`Que pierde ${nombreA || 'la primera'}`}
          ejemplo="el ultimo mundial que le queda"
          valor={r.precio.a}
          onChange={(v) => setAnidado('precio', 'a', v)}
        />
        <Campo
          etiqueta={`Que pierde ${nombreB || 'la segunda'}`}
          ejemplo="el puesto que le costo veinte anos"
          nota="de estos dos sale la pregunta dramatica: que acaben juntos ya lo sabemos, lo que no sabemos es que les cuesta"
          valor={r.precio.b}
          onChange={(v) => setAnidado('precio', 'b', v)}
        />
      </div>

      <h3 className="sub">La epoca</h3>
      <p className="ayuda">
        Sin esto G0 no abre: si la lista esta vacia, el validador no tiene
        anacronismos que vetar y la epoca es decorativa.
      </p>
      <div className="campos">
        <Campo
          ancho
          destacado
          filas={5}
          etiqueta="Que NO existia todavia"
          ejemplo="celular con camara · Instagram · YouTube · VAR · euro"
          nota="uno por linea. Son las palabras exactas que el validador veta en la prosa (V8)."
          valor={epoca.prohibido}
          onChange={(v) => setEpoca({ ...epoca, prohibido: v })}
        />
        <Campo
          ancho
          filas={2}
          etiqueta="Como era"
          ejemplo="Los partidos se seguian por radio; el resumen llegaba al dia siguiente en el diario."
          nota="como se seguia un partido, que se leia, como se pagaba. Es contexto para escribir, no una lista de cosas que meter."
          valor={epoca.notas}
          onChange={(v) => setEpoca({ ...epoca, notas: v })}
        />
        <Campo
          ancho
          filas={2}
          etiqueta="Fuentes"
          ejemplo="https://es.wikipedia.org/wiki/1998"
          nota="una por linea. Lo que no trae fuente no entra en el canon."
          valor={epoca.fuentes}
          onChange={(v) => setEpoca({ ...epoca, fuentes: v })}
        />
      </div>

      <h3 className="sub">Lo demas que esta en juego</h3>
      <div className="campos">
        <Campo
          etiqueta="Hilo 1"
          ejemplo="la lista de doce que hay que cerrar"
          valor={r.hilos[0]}
          onChange={(v) => setHilo(0, v)}
        />
        <Campo
          etiqueta="Hilo 2"
          ejemplo="el gimnasio del barrio que van a demoler"
          nota="exactamente dos, y su numero no crece durante la escritura: es lo que hace que el libro pueda terminar"
          valor={r.hilos[1]}
          onChange={(v) => setHilo(1, v)}
        />
      </div>
    </section>
  )
}
