// chokidar sobre books/.
//
// Cuando algo cambia, el servidor relee la novela entera y manda el modelo
// nuevo. No manda parches y no lleva la cuenta de nada.
//
// Releer entero es mas caro y es deliberado: es la misma decision que tomo el
// sistema al no tener archivo de estado. Una novela son doscientos archivos de
// texto y releerlos cuesta milisegundos; a cambio, el tablero no puede
// desincronizarse de la carpeta, que es la unica garantia que importa.

import chokidar from 'chokidar'
import path from 'node:path'

/** Lo que tarda en calmarse una rafaga de cambios antes de releer. */
const REBOTE_MS = 150

export function vigilar(libros: string, alCambiar: (slug: string) => void): () => Promise<void> {
  const vigia = chokidar.watch(libros, {
    ignoreInitial: true,
    // Un archivo que se esta escribiendo todavia no es un acontecimiento.
    awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 40 },
  })

  const rebotes = new Map<string, NodeJS.Timeout>()

  const aviso = (ruta: string) => {
    const relativa = path.relative(libros, ruta)
    if (relativa.startsWith('..')) return
    const slug = relativa.split(path.sep)[0]
    if (!slug) return

    // Los renombrados de aprobacion (mv NN.borrador.md NN.md) llegan como un
    // borrado y una creacion. El vigia no los interpreta: agrupa, relee, y en
    // el modelo nuevo el capitulo ya esta aprobado.
    const pendiente = rebotes.get(slug)
    if (pendiente) clearTimeout(pendiente)
    rebotes.set(
      slug,
      setTimeout(() => {
        rebotes.delete(slug)
        alCambiar(slug)
      }, REBOTE_MS),
    )
  }

  vigia.on('add', aviso).on('change', aviso).on('unlink', aviso).on('addDir', aviso)

  return async () => {
    for (const t of rebotes.values()) clearTimeout(t)
    rebotes.clear()
    await vigia.close()
  }
}
