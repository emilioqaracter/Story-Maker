// Los tipos del modelo del tablero.
//
// Regla que manda sobre este archivo: ningun campo existe aqui si no esta en
// un archivo de books/. El tablero no deduce, no estima y no completa. Si algo
// no se puede leer, el campo es null y la pantalla dice que falta.

export type Veredicto = 'VERDE' | 'ROJA' | 'NO ENTENDIDA'

export type Juez = 'revisor' | 'verificador'

/** Un problema senalado por una luz roja. Los tres campos van siempre juntos. */
export type Bloque = {
  titulo: string
  donde: string
  queCambiar: string
}

export type Luz = {
  juez: Juez
  veredicto: Veredicto
  bloques: Bloque[]
  refuerzo: string | null
  leccion: string | null
  /** El archivo entero. No es opcional y no se descarta nunca. */
  crudo: string
  ruta: string
}

export type Intento = {
  k: number
  revisor: Luz | null
  verificador: Luz | null
}

export type Continuidad = {
  titulo: string
  cuandoYDonde: string
  hechos: string[]
  dondeTermina: string
  noRepetir: string[]
  crudo: string
  ruta: string
}

export type EstadoCapitulo = 'pendiente' | 'en curso' | 'aprobado' | 'parado'

export type Capitulo = {
  numero: number
  estado: EstadoCapitulo
  texto: string | null
  esBorrador: boolean
  palabras: number
  intentos: Intento[]
  continuidad: Continuidad | null
}

export type CapPlan = {
  numero: number
  titulo: string
  /** Las palabras que el plan pide. null si el encabezado no las trae. */
  palabras: number | null
  parte: string | null
}

export type UsoModelo = {
  modelo: string
  costeUSD: number
  entrada: number
  salida: number
  razonamiento: number
}

export type Despacho = {
  tipo: string
  n: number
}

export type Cuenta = {
  costeUSD: number
  /** El tiempo de API de la corrida entera, no el del ultimo turno. */
  duracionMs: number
  modelos: UsoModelo[]
  despachos: Despacho[]
  subagentes: number
  fallos: number
}

export type EstadoNovela = 'en curso' | 'terminada' | 'parada'

export type Novela = {
  slug: string
  titulo: string
  voz: string
  capitulosPrevistos: CapPlan[]
  capitulos: Capitulo[]
  /** novela.md, si existe. */
  cierre: string | null
  /** sesion.json, si existe y no esta vacio. null es "sin medir". */
  cuenta: Cuenta | null
  estado: EstadoNovela
}

/** Lo que el tablero lista sin abrir la novela entera. */
export type Resumen = {
  slug: string
  titulo: string
  estado: EstadoNovela
  capitulos: number
  capitulosPrevistos: number
  intentos: number
  /** Capitulos que entraron al primer intento. */
  aLaPrimera: number
  costeUSD: number | null
}

/**
 * Una novela, tal como esta en disco: ruta relativa a la carpeta de la novela
 * (con barras normales) contra el contenido del archivo.
 *
 * Es la unica entrada del lector. El servidor la llena leyendo disco y el modo
 * estatico la llena desde el volcado, asi que las dos rutas producen el modelo
 * con exactamente el mismo codigo.
 */
export type Archivos = Record<string, string>
