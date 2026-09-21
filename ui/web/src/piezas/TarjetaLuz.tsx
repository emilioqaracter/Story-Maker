// El motivo de una luz, con las palabras del juez.
//
// El tablero no resume ni reescribe un motivo. La cita y el que cambiar se
// muestran tal como los escribio el juez: se pueden recortar por espacio
// -eso lo hace el CSS-, nunca reformular.

import { cuerpoDeLuz } from '../lector/index.ts'
import type { Luz } from '../lector/index.ts'
import { Punto } from './Punto.tsx'

function Cabecera({ luz, capitulo, intento }: { luz: Luz; capitulo?: number; intento?: number }) {
  const donde = [
    capitulo !== undefined ? `cap ${String(capitulo).padStart(2, '0')}` : null,
    intento !== undefined ? `intento ${intento}` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="flex items-center gap-2 font-[family-name:var(--font-maquina)] text-[12px] tracking-wide">
      <Punto estado={luz.veredicto} />
      <span className={luz.veredicto === 'ROJA' ? 'text-naranja' : 'text-texto'}>
        {luz.veredicto}
      </span>
      <span className="text-texto-suave">{luz.juez}</span>
      {donde && <span className="text-texto-suave">· {donde}</span>}
    </div>
  )
}

/**
 * La cita del capitulo.
 *
 * El sistema no guarda los borradores rechazados: NN.borrador.md se renombra a
 * NN.md y la version anterior desaparece. Lo unico que sobrevive del texto
 * rechazado es esto, asi que se ensena con el aspecto de lo que es: un
 * fragmento, entre comillas, de un texto que ya no existe.
 */
function Cita({ texto }: { texto: string }) {
  if (!texto) return null
  return (
    <p className="mt-1 border-l-2 border-borde pl-3 font-[family-name:var(--font-libro)] text-[13px] leading-snug text-texto-suave italic">
      {texto.startsWith('«') ? texto : `«${texto}»`}
    </p>
  )
}

export function TarjetaLuz({
  luz,
  capitulo,
  intento,
  lineas = 0,
  conCabecera = true,
}: {
  luz: Luz
  capitulo?: number
  intento?: number
  /** Cuantas lineas deja ver del "que cambiar". 0 es sin limite. */
  lineas?: number
  /** En el expediente la cabecera ya la pone la fila que abre la luz. */
  conCabecera?: boolean
}) {
  return (
    <div className="flex h-full flex-col gap-3 overflow-hidden">
      {conCabecera && <Cabecera luz={luz} capitulo={capitulo} intento={intento} />}

      {luz.veredicto === 'NO ENTENDIDA' && (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <p className="font-[family-name:var(--font-maquina)] text-[11px] text-naranja">
            La primera linea de este archivo no es «LUZ: VERDE» ni «LUZ: ROJA».
            El tablero no deduce el veredicto: ensena el archivo como esta.
          </p>
          <pre className="mt-2 font-[family-name:var(--font-maquina)] text-[11px] whitespace-pre-wrap text-texto-suave">
            {luz.crudo}
          </pre>
        </div>
      )}

      {luz.veredicto === 'ROJA' && (
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1">
          {luz.bloques.map((b, i) => (
            <div key={i}>
              <p className="font-[family-name:var(--font-libro)] text-[14px] leading-snug text-texto">
                {b.titulo}
              </p>
              <Cita texto={b.donde} />
              {b.queCambiar && (
                <p
                  className="mt-1.5 font-[family-name:var(--font-libro)] text-[13px] leading-snug text-texto-suave"
                  style={lineas > 0 ? recorte(lineas) : undefined}
                >
                  <span className="text-texto">Qué cambiar: </span>
                  {b.queCambiar}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {luz.veredicto === 'VERDE' && (
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <p className="font-[family-name:var(--font-libro)] text-[13px] leading-snug text-texto-suave">
            {cuerpoDeLuz(luz)}
          </p>
        </div>
      )}

      {(luz.refuerzo || luz.leccion) && (
        <div className="shrink-0 border-t border-borde pt-2">
          {luz.refuerzo && (
            <p className="font-[family-name:var(--font-libro)] text-[12px] leading-snug text-texto-suave">
              <span className="text-texto">Refuerzo: </span>
              {luz.refuerzo}
            </p>
          )}
          {luz.leccion && (
            <p className="mt-1 font-[family-name:var(--font-libro)] text-[12px] leading-snug text-texto-suave">
              <span className="text-texto">Lección: </span>
              {luz.leccion}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function recorte(lineas: number): React.CSSProperties {
  return {
    display: '-webkit-box',
    WebkitLineClamp: lineas,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
  }
}
