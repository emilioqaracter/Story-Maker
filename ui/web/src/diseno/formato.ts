// Como se escribe un numero en pantalla.
//
// Todo lo que sale de aqui es monoespaciado por contrato: es lo que midio la
// maquina. La serif es para lo que escribio un agente, y nunca al reves. El
// lector aprende la regla en diez segundos sin que nadie se la diga.

const DECIMAL = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const ENTERO = new Intl.NumberFormat('es-ES')

export function usd(n: number): string {
  return `${DECIMAL.format(n)} USD`
}

export function entero(n: number): string {
  return ENTERO.format(n)
}

/** Los tokens se cuentan en miles: 114.109 no se lee, 114k si. */
export function miles(n: number): string {
  if (n < 1000) return ENTERO.format(n)
  return `${ENTERO.format(Math.round(n / 1000))}k`
}

export function duracion(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '—'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const resto = s % 60
  if (m < 60) return resto === 0 ? `${m} min` : `${m}m ${String(resto).padStart(2, '0')}s`
  const h = Math.floor(m / 60)
  return `${h}h ${String(m % 60).padStart(2, '0')}m`
}

/** Lo que no esta medido se ensena como no medido. Nunca como cero. */
export const SIN_MEDIR = 'sin medir'

export function usdOSinMedir(n: number | null | undefined): string {
  return n === null || n === undefined ? SIN_MEDIR : usd(n)
}
