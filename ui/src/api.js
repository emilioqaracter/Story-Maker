const BASE = '/api'

async function pedir(ruta, opciones) {
  const r = await fetch(BASE + ruta, {
    headers: { 'Content-Type': 'application/json' },
    ...opciones,
  })
  if (!r.ok && r.status >= 500) throw new Error('El harness no responde')
  return r.json()
}

export const api = {
  config: () => pedir('/config'),
  libros: () => pedir('/books'),
  libro: (slug) => pedir(`/books/${slug}`),
  crear: (datos) => pedir('/books', { method: 'POST', body: JSON.stringify(datos) }),
  correr: (slug) => pedir(`/books/${slug}/run`, { method: 'POST' }),
  reset: (slug) => pedir(`/books/${slug}/reset`, { method: 'POST' }),
  log: (slug) => pedir(`/books/${slug}/log`),
  novela: (slug) => pedir(`/books/${slug}/novela`),
}

// La misma cuenta que hace harness/scripts/common.py. Se repite aqui solo para
// mostrarla en vivo mientras se escribe el formulario; la que manda es la del
// servidor, que es la que ve el validador.
export function derivar(est, tol) {
  const lineas = est.parrafos_por_escena * est.lineas_por_parrafo
  const ppe = lineas * est.palabras_por_linea
  const ppeMax = lineas * (est.palabras_por_linea + (tol?.palabras_por_linea ?? 0))
  const total = est.capitulos * est.escenas_por_capitulo
  return {
    lineas_por_escena: lineas,
    palabras_por_escena: ppe,
    palabras_por_escena_max: ppeMax,
    escenas_totales: total,
    palabras_libro: ppe * total,
    techo_palabras: ppeMax * total,
  }
}
