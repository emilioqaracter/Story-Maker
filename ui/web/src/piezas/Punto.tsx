// Una luz, dibujada.
//
// El color nunca va solo. Una verde es un circulo lleno y una roja es un
// circulo hueco con un anillo grueso, y se distinguen en blanco y negro. El
// video puede acabar comprimido en una aplicacion de mensajeria, y el naranja
// y el verde son justo los dos tonos que peor sobreviven a eso: si la forma no
// los separase, en un movil serian el mismo gris.

import type { Casilla } from '../reloj/guion.ts'

export function Punto({ estado, tam = 12 }: { estado: Casilla; tam?: number }) {
  const base = { width: tam, height: tam, borderRadius: '50%' } as const

  switch (estado) {
    case 'VERDE':
      return (
        <span
          title="luz verde"
          className="inline-block align-middle"
          style={{ ...base, background: 'var(--color-verde)' }}
        />
      )

    case 'ROJA':
      return (
        <span
          title="luz roja"
          className="inline-block align-middle"
          style={{
            ...base,
            background: 'transparent',
            border: `${Math.max(2, Math.round(tam / 4))}px solid var(--color-naranja)`,
          }}
        />
      )

    case 'NO ENTENDIDA':
      // No se deduce el veredicto. Se dice que no se entendio.
      return (
        <span
          title="luz no entendida"
          className="inline-block text-center font-[family-name:var(--font-maquina)] leading-none text-texto-suave"
          style={{ width: tam, height: tam, fontSize: tam }}
        >
          ?
        </span>
      )

    case 'esperando':
      return (
        <span
          title="el juez esta leyendo"
          className="inline-block align-middle"
          style={{ ...base, border: '1px dashed var(--color-borde)' }}
        />
      )

    case 'pendiente':
    default:
      return (
        <span
          className="inline-block align-middle opacity-40"
          style={{ ...base, border: '1px solid var(--color-borde)' }}
        />
      )
  }
}
