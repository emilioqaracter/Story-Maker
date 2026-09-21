// La rejilla de luces: una fila por intento, que va creciendo hacia abajo.
//
// Al final de la novela esta rejilla ES el contenido de decisiones/, y se lee
// de un vistazo: donde costo y quien rechazo mas.

import { AnimatePresence, motion } from 'motion/react'

import type { Fila } from '../reloj/guion.ts'
import { Punto } from './Punto.tsx'

/*
  Los dos jueces se animan con el mismo retardo, cero diferencia. Si uno
  entrase veinte milisegundos antes que el otro, la pantalla estaria contando
  que hay un orden, y no lo hay: los dos leen el mismo capitulo a la vez y sin
  hablarse. Es la regla del sistema traducida a animacion, y por eso las dos
  casillas comparten esta constante en vez de tener una cada una.
*/
const CAIDA = { duration: 0.28, ease: [0.2, 0, 0, 1] } as const

export function RejillaLuces({ filas, resaltada }: { filas: Fila[]; resaltada?: string | null }) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="grid shrink-0 grid-cols-[2.5rem_2.5rem_2rem_2rem_1fr] gap-x-2 border-b border-borde pb-1 font-[family-name:var(--font-maquina)] text-[11px] tracking-wide text-texto-suave">
        <span>cap</span>
        <span>int</span>
        <span className="text-center">REV</span>
        <span className="text-center">VER</span>
        <span />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pt-1">
        <AnimatePresence initial={false}>
          {filas.map((f) => {
            const clave = `${f.capitulo}.${f.intento}`
            return (
              <motion.div
                key={clave}
                layout
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={CAIDA}
                className={
                  'grid grid-cols-[2.5rem_2.5rem_2rem_2rem_1fr] items-center gap-x-2 py-[3px] font-[family-name:var(--font-maquina)] text-[12px] ' +
                  (resaltada === clave ? 'text-texto' : 'text-texto-suave')
                }
              >
                <span>{String(f.capitulo).padStart(2, '0')}</span>
                <span>{f.intento}</span>
                {/* Las dos casillas, con la misma transicion y sin retardo. */}
                <motion.span className="text-center" transition={CAIDA}>
                  <Punto estado={f.revisor} />
                </motion.span>
                <motion.span className="text-center" transition={CAIDA}>
                  <Punto estado={f.verificador} />
                </motion.span>
                <span className="pl-1 text-[11px] text-verde">{f.aprobado ? 'aprobado' : ''}</span>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}
