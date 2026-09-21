// Pasa el lector por todas las novelas que hay en books/ y cuenta lo que
// encuentra. No es una prueba con datos de ejemplo: son las corridas reales,
// que es lo unico contra lo que vale la pena comprobar un parser.
//
//   npm run comprobar

import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { leerNovelaDeDisco, listarSlugs } from '../servidor/src/lector/index.ts'
import { aLaPrimera, intentosDe } from '../web/src/lector/index.ts'

const raizRepo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const libros = path.join(raizRepo, 'books')

const slugs = await listarSlugs(libros)
if (slugs.length === 0) {
  console.error(`No hay ninguna novela en ${libros}`)
  process.exit(1)
}

let noEntendidas = 0
let rojasSinCita = 0

console.log(
  ['novela', 'estado', 'caps', 'prev', 'int', '1ra', 'verdes', 'rojas', '?', 'cont', 'coste'].join(
    '\t',
  ),
)

for (const slug of slugs) {
  const n = await leerNovelaDeDisco(libros, slug)
  const luces = n.capitulos.flatMap((c) => c.intentos.flatMap((i) => [i.revisor, i.verificador]))
  const presentes = luces.filter((l) => l !== null)
  const verdes = presentes.filter((l) => l.veredicto === 'VERDE').length
  const rojas = presentes.filter((l) => l.veredicto === 'ROJA').length
  const raras = presentes.filter((l) => l.veredicto === 'NO ENTENDIDA').length
  noEntendidas += raras

  for (const l of presentes) {
    if (l.veredicto !== 'ROJA') continue
    // "Sin cita no hay rechazo" es una regla de la skill luz. Si un bloque
    // llega sin donde, el tablero lo ensena igual, pero conviene saberlo.
    if (l.bloques.length === 0 || l.bloques.some((b) => b.donde === '')) rojasSinCita++
  }

  console.log(
    [
      slug,
      n.estado,
      n.capitulos.filter((c) => c.estado === 'aprobado').length,
      n.capitulosPrevistos.length,
      intentosDe(n),
      aLaPrimera(n),
      verdes,
      rojas,
      raras,
      n.capitulos.filter((c) => c.continuidad).length,
      n.cuenta ? n.cuenta.costeUSD.toFixed(2) : 'sin medir',
    ].join('\t'),
  )
}

console.log('')
console.log(`luces no entendidas: ${noEntendidas}`)
console.log(`rojas con algun bloque sin cita: ${rojasSinCita}`)

// Una luz no entendida no es un fallo del tablero: es un archivo que no sigue
// el formato, y la pantalla lo dice. Pero si aparecen, hay que mirarlas.
if (noEntendidas > 0) console.log('(se ensenan en crudo y marcadas, no se deducen)')
