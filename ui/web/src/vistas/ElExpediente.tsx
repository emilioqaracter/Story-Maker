// La novela terminada, leible, y al lado la historia de cada capitulo.
//
// El capitulo se lee como un libro y se audita como un expediente: a la
// izquierda prosa con tipografia de libro, a la derecha todos los juicios que
// recibio, en orden, con sus motivos, y al final los hechos que el verificador
// dejo anotados en continuidad/.
//
// Y la novela entera tambien se lee aqui. Estaba leida del disco desde el
// principio -novela.md, el campo `cierre`- pero no habia forma de verla, que
// es un sitio raro donde esconder el producto.

import { useState } from 'react'

import { entero } from '../diseno/formato.ts'
import { cuerpoDeLuz } from '../lector/index.ts'
import type { Capitulo, Luz, Novela } from '../lector/index.ts'
import { Papel } from '../piezas/Papel.tsx'
import { Punto } from '../piezas/Punto.tsx'
import { TarjetaLuz } from '../piezas/TarjetaLuz.tsx'

export function ElExpediente({
  novela,
  capitulo,
  alCambiarCapitulo,
  verCierre,
  alVerCierre,
  verCrudo,
  alAlternarCrudo,
}: {
  novela: Novela
  capitulo: Capitulo | null
  alCambiarCapitulo: (numero: number) => void
  verCierre: boolean
  alVerCierre: (ver: boolean) => void
  verCrudo: boolean
  alAlternarCrudo: () => void
}) {
  if (verCierre && novela.cierre) {
    return (
      <div className="flex min-h-0 flex-1">
        <div className="flex w-[52%] shrink-0 flex-col">
          <Papel
            texto={novela.cierre}
            esNovela
            pie={
              <button
                type="button"
                onClick={() => alVerCierre(false)}
                className="hover:text-tinta"
              >
                ◄ volver a los capítulos
              </button>
            }
          />
        </div>
        <Indice novela={novela} alCambiarCapitulo={alCambiarCapitulo} />
      </div>
    )
  }

  if (!capitulo) {
    return (
      <div className="flex flex-1 items-center justify-center font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
        esta novela todavía no tiene capítulos en disco
      </div>
    )
  }

  const numeros = novela.capitulos.map((c) => c.numero)
  const i = numeros.indexOf(capitulo.numero)
  const anterior = i > 0 ? numeros[i - 1] : null
  const siguiente = i >= 0 && i < numeros.length - 1 ? numeros[i + 1] : null

  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex w-[52%] shrink-0 flex-col">
        <Papel
          texto={capitulo.texto}
          capitulo={capitulo}
          pie={
            <span className="flex items-center gap-5">
              <button
                type="button"
                disabled={anterior === null}
                onClick={() => anterior !== null && alCambiarCapitulo(anterior)}
                className="disabled:opacity-30"
              >
                ◄ cap {anterior ?? '—'}
              </button>
              <button
                type="button"
                disabled={siguiente === null}
                onClick={() => siguiente !== null && alCambiarCapitulo(siguiente)}
                className="disabled:opacity-30"
              >
                cap {siguiente ?? '—'} ►
              </button>
              {novela.cierre && (
                <button
                  type="button"
                  onClick={() => alVerCierre(true)}
                  className="rounded-sm border border-tinta-suave/40 px-2 py-1 hover:border-tinta hover:text-tinta"
                >
                  la novela entera
                </button>
              )}
            </span>
          }
        />
      </div>
      <Juicios capitulo={capitulo} verCrudo={verCrudo} alAlternarCrudo={alAlternarCrudo} />
    </div>
  )
}

// --- el indice de la novela entera ---------------------------------------

function Indice({
  novela,
  alCambiarCapitulo,
}: {
  novela: Novela
  alCambiarCapitulo: (n: number) => void
}) {
  const total = novela.capitulos.reduce((n, c) => n + c.palabras, 0)
  const intentos = novela.capitulos.reduce((n, c) => n + c.intentos.length, 0)

  return (
    <aside className="flex min-w-0 flex-1 flex-col bg-superficie p-6">
      <p className="font-[family-name:var(--font-maquina)] text-[11px] tracking-[0.14em] text-texto-suave">
        Lo que hay detrás
      </p>
      <p className="mt-2 font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
        {entero(total)} palabras · {novela.capitulos.length} capítulos · {intentos} intentos
      </p>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
        {novela.capitulos.map((c) => {
          const previsto = novela.capitulosPrevistos.find((p) => p.numero === c.numero)
          const luces = c.intentos.flatMap((it) => [it.revisor, it.verificador])
          const rojas = luces.filter((l) => l?.veredicto === 'ROJA').length
          return (
            <button
              key={c.numero}
              type="button"
              onClick={() => alCambiarCapitulo(c.numero)}
              className="mb-3 block w-full border-b border-borde pb-3 text-left last:border-0"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-[family-name:var(--font-libro)] text-[14px] text-texto">
                  {c.numero}. {previsto?.titulo ?? `Capítulo ${c.numero}`}
                </span>
                <span className="shrink-0 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave tabular-nums">
                  {entero(c.palabras)} p.
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-2 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
                <span>
                  {c.intentos.length} {c.intentos.length === 1 ? 'intento' : 'intentos'}
                </span>
                {rojas > 0 && (
                  <>
                    <span className="opacity-40">·</span>
                    <span className="flex items-center gap-1 text-naranja">
                      <Punto estado="ROJA" tam={8} />
                      {rojas} {rojas === 1 ? 'rechazo' : 'rechazos'}
                    </span>
                  </>
                )}
                {rojas === 0 && (
                  <>
                    <span className="opacity-40">·</span>
                    <span className="flex items-center gap-1">
                      <Punto estado="VERDE" tam={8} />a la primera
                    </span>
                  </>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

// --- los juicios ---------------------------------------------------------

function Juicios({
  capitulo,
  verCrudo,
  alAlternarCrudo,
}: {
  capitulo: Capitulo
  verCrudo: boolean
  alAlternarCrudo: () => void
}) {
  const [abierta, setAbierta] = useState<string | null>(null)

  const luces: { luz: Luz; intento: number }[] = capitulo.intentos.flatMap((i) =>
    (['revisor', 'verificador'] as const)
      .map((j) => i[j])
      .filter((l): l is Luz => l !== null)
      .map((luz) => ({ luz, intento: i.k })),
  )

  const elegida = luces.find((l) => l.luz.ruta === abierta)?.luz ?? null

  if (verCrudo) {
    return (
      <aside className="flex min-w-0 flex-1 flex-col bg-superficie p-6">
        <BotonCrudo verCrudo={verCrudo} alAlternar={alAlternarCrudo} />
        <p className="mt-2 mb-3 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
          {elegida ? elegida.ruta : 'elige una luz para ver su archivo'}
        </p>
        <pre className="min-h-0 flex-1 overflow-auto font-[family-name:var(--font-maquina)] text-[11px] leading-relaxed whitespace-pre-wrap text-texto-suave">
          {elegida?.crudo ?? ''}
        </pre>
      </aside>
    )
  }

  return (
    <aside className="flex min-w-0 flex-1 flex-col bg-superficie p-6">
      <BotonCrudo verCrudo={verCrudo} alAlternar={alAlternarCrudo} />

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1">
        {capitulo.intentos.map((intento, n) => (
          <div key={intento.k}>
            {n > 0 && <div className="my-4 h-px bg-borde" />}
            {(['revisor', 'verificador'] as const).map((juez) => {
              const luz = intento[juez]
              if (!luz) return null
              const esRoja = luz.veredicto !== 'VERDE'
              const estaAbierta = abierta === luz.ruta
              return (
                <div key={juez} className="mb-3">
                  <button
                    type="button"
                    onClick={() => setAbierta(estaAbierta ? null : luz.ruta)}
                    className="flex w-full items-center gap-2 text-left font-[family-name:var(--font-maquina)] text-[12px]"
                  >
                    <Punto estado={luz.veredicto} />
                    <span className={luz.veredicto === 'ROJA' ? 'text-naranja' : 'text-texto'}>
                      {luz.veredicto}
                    </span>
                    <span className="text-texto-suave">{juez}</span>
                    <span className="text-texto-suave">· intento {intento.k}</span>
                  </button>

                  {/* Una roja se abre sola. Una verde solo si se pide: ocupa
                      lo mismo y no cuenta nada. */}
                  {(esRoja || estaAbierta) && (
                    <div className="mt-2 pl-5">
                      {esRoja ? (
                        <TarjetaLuz luz={luz} conCabecera={false} />
                      ) : (
                        <p className="font-[family-name:var(--font-libro)] text-[13px] leading-snug text-texto-suave">
                          {cuerpoDeLuz(luz)}
                          {luz.refuerzo && (
                            <span className="mt-2 block">
                              <span className="text-texto">Refuerzo: </span>
                              {luz.refuerzo}
                            </span>
                          )}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {intento === capitulo.intentos[capitulo.intentos.length - 1] &&
              capitulo.estado === 'aprobado' && (
                <p className="mt-2 pl-5 font-[family-name:var(--font-maquina)] text-[12px] text-verde">
                  ✓ el capítulo entra
                </p>
              )}
          </div>
        ))}

        {capitulo.continuidad && (
          <div className="mt-6 border-t border-borde pt-4">
            <p className="mb-2 font-[family-name:var(--font-maquina)] text-[11px] tracking-wide text-texto-suave">
              Lo que este capítulo deja fijado
            </p>
            <ul className="space-y-1.5">
              {capitulo.continuidad.hechos.map((h, k) => (
                <li
                  key={k}
                  className="font-[family-name:var(--font-libro)] text-[13px] leading-snug text-texto-suave"
                >
                  · {h}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </aside>
  )
}

/**
 * `crudo` no es opcional y no se descarta nunca: es lo que permite comprobar
 * que el tablero no se invento nada.
 */
function BotonCrudo({ verCrudo, alAlternar }: { verCrudo: boolean; alAlternar: () => void }) {
  return (
    <button
      type="button"
      onClick={alAlternar}
      className="self-start font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave underline decoration-borde underline-offset-4 hover:text-texto"
    >
      {verCrudo ? '← volver a los juicios' : 'ver el archivo tal como está en disco (C)'}
    </button>
  )
}
