import Campo from './Campo.jsx'

const NIVELES = ['amateur', 'profesional', 'seleccion', 'juvenil']

export const EJEMPLO = {
  slug: 'vera-1998',
  respuestas: {
    deporte: 'basquetbol',
    epoca: { desde: '1998-01-01', hasta: '1998-12-31' },
    lugar: 'Montevideo, Uruguay',
    nivel: 'seleccion',
    protagonista: { nombre: 'Vera Olmos', rol: 'base de la seleccion, la mas veterana del plantel' },
    secundarios: [{ nombre: 'Ruben Alcaide', rol: 'entrenador de la seleccion, primer ciclo a cargo' }],
    meta: 'jugar el mundial que va a ser el ultimo de su carrera',
    obstaculo: 'el entrenador la dejo fuera de la lista y el medico no le firma el alta',
    precio: 'el gimnasio que levanto en su barrio, que no puede sostener si se va seis meses',
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

  const nombre = r.protagonista.nombre.split(' ')[0]
  const setSecundario = (i, sub, valor) => {
    const s = [...(r.secundarios || [])]
    s[i] = { ...s[i], [sub]: valor }
    set('secundarios', s)
  }

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

      <h3 className="sub">El protagonista</h3>
      <p className="ayuda">
        La novela es de una sola persona: su historia, su punto de vista. Los
        demas son personajes.
      </p>
      <div className="campos dos">
        <fieldset>
          <legend>Quien es</legend>
          <Campo
            etiqueta="Nombre y apellido"
            ejemplo="Vera Olmos"
            valor={r.protagonista.nombre}
            onChange={(v) => setAnidado('protagonista', 'nombre', v)}
          />
          <Campo
            etiqueta="Que hace en ese mundo"
            ejemplo="base de la seleccion, la mas veterana del plantel"
            valor={r.protagonista.rol}
            onChange={(v) => setAnidado('protagonista', 'rol', v)}
          />
        </fieldset>
        <fieldset>
          <legend>Quien mas hay (opcional)</legend>
          <Campo
            etiqueta="Nombre y apellido"
            ejemplo="Ruben Alcaide"
            valor={(r.secundarios || [{}])[0]?.nombre || ''}
            onChange={(v) => setSecundario(0, 'nombre', v)}
          />
          <Campo
            etiqueta="Que hace en ese mundo"
            ejemplo="entrenador de la seleccion, primer ciclo a cargo"
            valor={(r.secundarios || [{}])[0]?.rol || ''}
            onChange={(v) => setSecundario(0, 'rol', v)}
          />
        </fieldset>
      </div>

      <h3 className="sub">La historia</h3>
      <p className="ayuda">
        De estas tres sale todo el arco. Los tres actos no se declaran: se
        calculan repartiendo la epoca (25/50/25).
      </p>
      <div className="campos">
        <Campo
          ancho
          destacado
          etiqueta={`Que quiere ${nombre || 'el protagonista'}`}
          ejemplo="jugar el mundial que va a ser el ultimo de su carrera"
          nota="Concreta y comprobable: si no se puede saber si lo consiguio, el desenlace no puede existir."
          valor={r.meta}
          onChange={(v) => set('meta', v)}
        />
        <Campo
          ancho
          destacado
          filas={2}
          etiqueta="Que se lo impide"
          ejemplo="el entrenador la dejo fuera de la lista y el medico no le firma el alta"
          nota="Mejor algo estructural — un cuerpo roto, un contrato, una federacion — que una duda que se resuelve decidiendo."
          valor={r.obstaculo}
          onChange={(v) => set('obstaculo', v)}
        />
        <Campo
          ancho
          filas={2}
          etiqueta="Que le va a costar"
          ejemplo="el gimnasio que levanto en su barrio, que no puede sostener si se va seis meses"
          nota="Si no pierde nada, no hay historia: hay un entrenamiento largo."
          valor={r.precio}
          onChange={(v) => set('precio', v)}
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
