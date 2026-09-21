// El ciclo de aprobacion de un capitulo, en marcha.
//
// La imagen que explica el sistema entero es que los dos jueces se encienden a
// la vez. Si se encendieran uno despues del otro, la pantalla estaria contando
// una mentira sobre como funciona.

import { ReactFlow, type Edge, type Node } from '@xyflow/react'
import { useMemo } from 'react'

import { NodoAgente, type DatosNodo, type EstadoNodo } from './NodoAgente.tsx'

/**
 * Quien esta trabajando ahora mismo, por nombre de agente.
 *
 * El grafo no sabe si eso viene del reloj del replay o del stream de una
 * corrida en marcha, y no le hace falta: dibuja quien esta encendido. En
 * replay los dos jueces entran y salen juntos, porque es lo que pasa. En vivo
 * entran juntos —la skill los despacha en el mismo mensaje— y salen cuando
 * cada uno termina, que tambien es lo que pasa.
 */
export type Trabajando = ReadonlySet<string>

const TIPOS = { agente: NodoAgente }

const vuelta = {
  stroke: 'var(--color-borde)',
  strokeWidth: 1,
  strokeDasharray: '4 4',
} as const

const SITIOS = {
  arquitecto: { x: 40, y: 0 },
  redactor: { x: 40, y: 120 },
  revisor: { x: 330, y: 60 },
  verificador: { x: 330, y: 190 },
} as const

/** Las aristas solo se animan cuando algo viaja por ellas. */
function arista(
  id: string,
  source: string,
  target: string,
  anclajes: { de: string; a: string },
  viva: boolean,
  extra?: Partial<Edge>,
): Edge {
  return {
    id,
    source,
    target,
    sourceHandle: anclajes.de,
    targetHandle: anclajes.a,
    animated: viva,
    type: 'smoothstep',
    style: {
      stroke: viva ? 'var(--color-naranja)' : 'var(--color-borde)',
      strokeWidth: viva ? 2 : 1,
    },
    ...extra,
  }
}

const IDA = { de: 'der', a: 'izq' }
const BAJADA = { de: 'abajo', a: 'arriba' }
const VUELTA = { de: 'abajo', a: 'izq' }

export function Grafo({
  trabajando,
  hayPlan,
}: {
  trabajando: Trabajando
  hayPlan: boolean
}) {
  const clave = [...trabajando].sort().join(',')

  const nodos = useMemo<Node<DatosNodo>[]>(() => {
    const estado = (quien: string): EstadoNodo => {
      if (trabajando.has(quien)) return 'trabajando'
      if (quien === 'arquitecto') return hayPlan ? 'hecho' : 'inactivo'
      return 'inactivo'
    }

    return [
      {
        id: 'arquitecto',
        type: 'agente',
        position: SITIOS.arquitecto,
        data: { etiqueta: 'arquitecto', estado: estado('arquitecto') },
        draggable: false,
      },
      {
        id: 'redactor',
        type: 'agente',
        position: SITIOS.redactor,
        data: { etiqueta: 'redactor', estado: estado('redactor') },
        draggable: false,
      },
      {
        id: 'revisor',
        type: 'agente',
        position: SITIOS.revisor,
        data: { etiqueta: 'revisor', estado: estado('revisor') },
        draggable: false,
      },
      {
        id: 'verificador',
        type: 'agente',
        position: SITIOS.verificador,
        data: { etiqueta: 'verificador', estado: estado('verificador') },
        draggable: false,
      },
    ]
    // `clave` resume el conjunto: sin el, useMemo no ve los cambios de un Set
    // que llega nuevo en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, hayPlan])

  const aristas = useMemo<Edge[]>(() => {
    const haciaRedactor = trabajando.has('redactor')
    const haciaJueces = trabajando.has('revisor') || trabajando.has('verificador')
    return [
      arista('plan', 'arquitecto', 'redactor', BAJADA, haciaRedactor && hayPlan),
      arista('a-revisor', 'redactor', 'revisor', IDA, haciaJueces),
      arista('a-verificador', 'redactor', 'verificador', IDA, haciaJueces),
      // La vuelta al redactor va punteada: es el camino que solo se recorre
      // cuando algo se rechaza, y verlo distinto del de ida es la mitad de lo
      // que cuenta el dibujo.
      arista('vuelta-revisor', 'revisor', 'redactor', VUELTA, false, { style: vuelta }),
      arista('vuelta-verificador', 'verificador', 'redactor', VUELTA, false, {
        style: vuelta,
        label: 'alguna roja',
        labelShowBg: true,
        labelStyle: {
          fill: 'var(--color-texto-suave)',
          fontSize: 11,
          fontFamily: 'var(--font-maquina)',
        },
        labelBgStyle: { fill: 'var(--color-fondo)' },
        labelBgPadding: [6, 3],
      }),
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, hayPlan])

  return (
    <ReactFlow
      nodes={nodos}
      edges={aristas}
      nodeTypes={TIPOS}
      fitView
      // maxZoom 1 deja los nodos a su tamano natural. Sin el, fitView amplia
      // para llenar el hueco y el grafo se come la pantalla.
      fitViewOptions={{ padding: 0.3, maxZoom: 1 }}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      panOnScroll={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      zoomOnDoubleClick={false}
      preventScrolling={false}
    />
  )
}
