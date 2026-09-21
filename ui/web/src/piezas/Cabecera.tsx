// La cabecera es la misma en las dos pestanas y el logo ocupa siempre el mismo
// punto: al pasar de una vista a otra no se mueve, y el recorrido entero del
// video queda cosido por el.
//
// El logo aparece aqui y en ningun otro sitio. Un logo repetido en cada panel
// es una marca de agua, no una marca; y dentro del panel del manuscrito no
// entra nunca, porque la prosa la escribio un agente y no la empresa.

import { Marca } from '../diseno/Marca.tsx'
import type { Pestana, Vista } from '../reloj/store.ts'

const VISTAS: { id: Vista; nombre: string; tecla: string }[] = [
  { id: 'circulo', nombre: 'el círculo', tecla: '1' },
  { id: 'expediente', nombre: 'la novela', tecla: '2' },
  { id: 'cuenta', nombre: 'la cuenta', tecla: '3' },
]

/**
 * Que esta enseñando el tablero ahora mismo.
 *
 * `espera` existe porque la pestana de escribir sin nada en marcha no es un
 * replay: no esta reproduciendo nada. Ponerle la etiqueta de replay seria
 * mentir en la direccion contraria a la habitual, pero mentir igual.
 */
export type Etiquetado = 'vivo' | 'replay' | 'espera'

export function Cabecera({
  pestana,
  vista,
  derecha,
  etiquetado,
  origen,
  grabacion,
  puedeEscribir,
  alPestana,
  alVista,
}: {
  pestana: Pestana
  vista: Vista
  derecha: string
  etiquetado: Etiquetado
  origen: string
  grabacion: boolean
  puedeEscribir: boolean
  alPestana: (p: Pestana) => void
  alVista: (v: Vista) => void
}) {
  return (
    <header className="flex shrink-0 items-center gap-4 border-b border-borde bg-superficie">
      <div className="flex items-center py-2.5">
        <Marca alto={grabacion ? 32 : 24} />
      </div>

      <div className="h-5 w-px shrink-0 bg-borde" />

      <span className="shrink-0 font-[family-name:var(--font-maquina)] text-[13px] tracking-[0.18em] text-texto">
        STORY-MAKER
      </span>

      {/* Las dos pestanas. Una lee lo que ya paso; la otra lo provoca. */}
      <nav className="flex shrink-0 items-center gap-1">
        <Pestanita activa={pestana === 'historial'} onClick={() => alPestana('historial')}>
          historial
        </Pestanita>
        <Pestanita
          activa={pestana === 'escribir'}
          onClick={() => alPestana('escribir')}
          apagada={!puedeEscribir}
          titulo={puedeEscribir ? undefined : 'hace falta el servidor para escribir una novela'}
        >
          escribir una nueva
        </Pestanita>
      </nav>

      {pestana === 'historial' && (
        <>
          <div className="h-4 w-px shrink-0 bg-borde" />
          <nav className="flex shrink-0 items-center gap-4">
            {VISTAS.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => alVista(v.id)}
                className={
                  'font-[family-name:var(--font-maquina)] text-[12px] tracking-wide ' +
                  (vista === v.id ? 'text-texto' : 'text-texto-suave hover:text-texto')
                }
              >
                {v.nombre}
                <span className="ml-1 opacity-50">{v.tecla}</span>
              </button>
            ))}
          </nav>
        </>
      )}

      <div className="min-w-0 flex-1" />

      <span className="truncate font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
        {derecha}
      </span>

      <Etiqueta etiquetado={etiquetado} origen={origen} />
    </header>
  )
}

function Pestanita({
  activa,
  apagada,
  titulo,
  onClick,
  children,
}: {
  activa: boolean
  apagada?: boolean
  titulo?: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={apagada}
      title={titulo}
      className={
        'rounded-sm px-3 py-1 font-[family-name:var(--font-maquina)] text-[12px] tracking-[0.12em] ' +
        (activa
          ? 'bg-superficie-alta text-texto'
          : 'text-texto-suave hover:text-texto disabled:opacity-40 disabled:hover:text-texto-suave')
      }
    >
      {children}
    </button>
  )
}

/**
 * El replay nunca se disfraza de directo: lleva su etiqueta en pantalla.
 *
 * La spec pide ademas la fecha en que corrio la novela, y esa fecha no existe
 * en ningun sitio: los archivos de decision no la llevan dentro y los mtime no
 * sobreviven a un clon. Asi que se dice lo que se sabe -de donde salen los
 * archivos- y se dice que la fecha falta, en vez de poner la del checkout.
 */
function Etiqueta({ etiquetado, origen }: { etiquetado: Etiquetado; origen: string }) {
  if (etiquetado === 'espera') {
    return (
      <span className="mr-6 shrink-0 font-[family-name:var(--font-maquina)] text-[11px] tracking-[0.14em] text-texto-suave/60">
        {origen}
      </span>
    )
  }
  const vivo = etiquetado === 'vivo'
  return (
    <span
      className={
        'mr-6 shrink-0 rounded-sm px-2 py-1 font-[family-name:var(--font-maquina)] text-[11px] tracking-[0.14em] ' +
        (vivo ? 'bg-naranja text-white' : 'border border-borde text-texto-suave')
      }
      title={vivo ? 'los archivos llegan segun aparecen' : `origen: ${origen}`}
    >
      {vivo ? 'EN VIVO' : `REPLAY · ${origen}`}
    </span>
  )
}
