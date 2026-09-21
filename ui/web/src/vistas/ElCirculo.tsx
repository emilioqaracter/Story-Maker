// La pantalla principal: el ciclo de aprobacion de un capitulo, en marcha.
//
// Por orden de importancia: los dos jueces se encienden a la vez, la luz cae y
// se ve de que color es, una roja abre su motivo, el capitulo vuelve al
// redactor, y el coste sube mientras tanto.

import { AnimatePresence, motion } from 'motion/react'

import { usd, duracion, entero, SIN_MEDIR } from '../diseno/formato.ts'
import type { Novela } from '../lector/index.ts'
import type { Instante } from '../reloj/guion.ts'
import { Grafo } from '../piezas/Grafo.tsx'
import { RejillaLuces } from '../piezas/RejillaLuces.tsx'
import { TarjetaLuz } from '../piezas/TarjetaLuz.tsx'

export function ElCirculo({ novela, instante }: { novela: Novela; instante: Instante }) {
  const previstos = novela.capitulosPrevistos.length || novela.capitulos.length
  const cuenta = novela.cuenta
  const resaltada =
    instante.capitulo !== null && instante.intento !== null
      ? `${instante.capitulo}.${instante.intento}`
      : null

  // "jueces" son los dos, siempre. En el replay no hay forma de encender uno
  // solo: si uno entrase antes que el otro, la pantalla estaria contando que
  // hay un orden, y no lo hay.
  const trabajando = new Set(
    instante.quienTrabaja === 'jueces'
      ? ['revisor', 'verificador']
      : instante.quienTrabaja
        ? [instante.quienTrabaja]
        : [],
  )

  return (
    <div className="flex min-h-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        {/* El grafo se encuadra en vez de llenar: suelto en toda la mitad
            izquierda queda perdido, y en el video lo que se mira es el nodo
            que se enciende, no el hueco que lo rodea. */}
        <div className="flex min-h-0 flex-1 items-center justify-center px-10">
          <div className="h-[23rem] w-full max-w-[46rem]">
            <Grafo
              trabajando={trabajando}
              hayPlan={novela.capitulosPrevistos.length > 0}
            />
          </div>
        </div>

        <div className="shrink-0 px-10 pb-8">
          <Progreso hechos={instante.aprobados} total={previstos} />
          <Coste cuenta={cuenta} avance={instante.avance} />
        </div>
      </section>

      <aside className="flex w-[27rem] shrink-0 flex-col border-l border-borde bg-superficie">
        <div className="flex h-[45%] shrink-0 flex-col p-4">
          <RejillaLuces filas={instante.filas} resaltada={resaltada} />
        </div>

        <div className="flex min-h-0 flex-1 flex-col border-t border-borde p-4">
          <AnimatePresence mode="wait">
            {instante.abierta ? (
              <motion.div
                key={instante.abierta.ruta}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25, ease: [0.2, 0, 0, 1] }}
                className="flex min-h-0 flex-1"
              >
                <TarjetaLuz
                  luz={instante.abierta}
                  capitulo={instante.capitulo ?? undefined}
                  intento={instante.intento ?? undefined}
                  lineas={4}
                />
              </motion.div>
            ) : (
              // El motivo de una luz verde no se abre solo: ocupa lo mismo que
              // una roja y no cuenta nada. Se abre si se pide, en el expediente.
              <motion.p
                key="hueco"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="m-auto font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave"
              >
                {instante.terminada ? 'la novela está cerrada' : 'sin rechazos que mostrar'}
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </aside>
    </div>
  )
}

function Progreso({ hechos, total }: { hechos: number; total: number }) {
  const fraccion = total === 0 ? 0 : hechos / total
  return (
    <div className="flex items-center gap-4">
      <div className="h-1.5 w-64 overflow-hidden rounded-full bg-superficie-alta">
        <motion.div
          className="h-full bg-verde"
          initial={false}
          animate={{ width: `${fraccion * 100}%` }}
          transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}
        />
      </div>
      <span className="font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
        {hechos} de {total} capítulos
      </span>
    </div>
  )
}

/**
 * El coste sube mientras tanto: un numero que crece solo hace que lo demas
 * parezca real.
 *
 * Lo que crece es el total medido repartido por lo que lleva reproducido el
 * replay, y la linea de abajo lo dice con todas las letras. El tablero no
 * inventa un numero: el unico dato que afirma es el total, y ese esta en
 * sesion.json. Si la novela no lo tiene, aqui no hay una estimacion: hay un
 * "sin medir".
 */
function Coste({ cuenta, avance }: { cuenta: Novela['cuenta']; avance: number }) {
  if (!cuenta) {
    return (
      <div className="mt-3">
        <p className="font-[family-name:var(--font-maquina)] text-[26px] leading-none text-texto-suave">
          {SIN_MEDIR}
        </p>
        <p className="mt-1.5 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
          esta novela no tiene sesion.json · el coste no se estima
        </p>
      </div>
    )
  }

  return (
    <div className="mt-3">
      <p className="font-[family-name:var(--font-maquina)] text-[26px] leading-none text-texto tabular-nums">
        {usd(cuenta.costeUSD * avance)}
      </p>
      <p className="mt-1.5 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
        de {usd(cuenta.costeUSD)} medidos · {duracion(cuenta.duracionMs)} ·{' '}
        {entero(cuenta.subagentes)} despachos
      </p>
    </div>
  )
}
