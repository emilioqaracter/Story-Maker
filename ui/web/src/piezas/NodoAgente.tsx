// Un agente del ciclo, como nodo del grafo.
//
// El naranja de un nodo significa "esta corriendo ahora". El mismo naranja, en
// la rejilla, significa luz roja: no se confunden porque estan en sitios
// distintos y con formas distintas -aqui un borde, alli un anillo hueco-, y
// porque nunca hay mas de dos cosas naranjas a la vez en pantalla.
//
// Y nada parpadea. Un tablero que parpadea parece que falla.

import { Handle, Position } from '@xyflow/react'

export type EstadoNodo = 'inactivo' | 'trabajando' | 'hecho'

export type DatosNodo = {
  etiqueta: string
  estado: EstadoNodo
  nota?: string
}

export function NodoAgente({ data }: { data: DatosNodo }) {
  const { etiqueta, estado, nota } = data

  const borde =
    estado === 'trabajando'
      ? '2px solid var(--color-naranja)'
      : '1px solid var(--color-borde)'

  return (
    <div className="relative">
      {/* Los anclajes van con nombre para que cada arista entre y salga por
          donde tiene que hacerlo: la ida por la derecha, la vuelta por abajo.
          Sin nombrarlos, React Flow elige el mas corto y el dibujo deja de
          contar el ciclo. */}
      <Handle id="arriba" type="target" position={Position.Top} className="!opacity-0" />
      <Handle id="izq" type="target" position={Position.Left} className="!opacity-0" />
      <div
        className="flex min-w-[9.5rem] items-center justify-center rounded-sm px-4 py-2.5 font-[family-name:var(--font-maquina)] text-[12px] tracking-[0.14em] transition-colors duration-200"
        style={{
          border: borde,
          background: estado === 'trabajando' ? 'var(--color-superficie-alta)' : 'transparent',
          color: estado === 'inactivo' ? 'var(--color-texto-suave)' : 'var(--color-texto)',
        }}
      >
        {etiqueta.toUpperCase()}
      </div>

      {estado === 'hecho' && (
        <span className="absolute top-1/2 -right-5 -translate-y-1/2 font-[family-name:var(--font-maquina)] text-[13px] text-verde">
          ✓
        </span>
      )}
      {nota && (
        <span className="absolute -bottom-4 left-0 font-[family-name:var(--font-maquina)] text-[10px] text-texto-suave">
          {nota}
        </span>
      )}

      <Handle id="der" type="source" position={Position.Right} className="!opacity-0" />
      <Handle id="abajo" type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  )
}
