// La barra de abajo del historial: elegir corrida y mover el reloj del replay.
//
// Lleva la clase `solo-desarrollo`, asi que el modo grabacion (tecla G) la
// esconde entera. No forma parte de lo que cuenta el video.
//
// Aqui ya no se lanza nada: escribir una novela es la otra pestana, con su
// propia pantalla. Meter un campo de texto en una barra de estado hacia que
// nadie encontrase la mitad del producto.

import { duracion } from '../diseno/formato.ts'
import type { Resumen } from '../lector/index.ts'
import { duracionDe } from '../reloj/guion.ts'
import { usarTablero } from '../reloj/store.ts'

export function BarraDesarrollo({
  resumenes,
  slug,
  alElegir,
  escribiendo,
}: {
  resumenes: Resumen[]
  slug: string | null
  alElegir: (slug: string) => void
  escribiendo: string | null
}) {
  const t = usarTablero()
  const total = duracionDe(t.guion)

  return (
    <footer className="solo-desarrollo flex shrink-0 items-center gap-5 border-t border-borde bg-superficie px-6 py-2 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
      <select
        value={slug ?? ''}
        onChange={(e) => alElegir(e.target.value)}
        className="rounded-sm border border-borde bg-fondo px-2 py-1 text-texto"
      >
        {resumenes.map((r) => (
          <option key={r.slug} value={r.slug}>
            {r.slug} · {r.estado}
          </option>
        ))}
      </select>

      <button type="button" onClick={t.alternarReproduccion} className="hover:text-texto">
        {t.corriendo ? '❙❙ pausa' : '▶ reproducir'}
      </button>

      <span>
        ×{t.velocidad} · {t.indice + 1}/{t.guion.length} · {duracion(total / t.velocidad)} de
        replay
      </span>

      <span className="flex-1" />

      {escribiendo && (
        <span className="text-naranja">escribiendo {escribiendo || 'una novela nueva'}</span>
      )}

      <span className="opacity-70">1 2 3 · espacio · ← → · + − · G · C</span>
    </footer>
  )
}
