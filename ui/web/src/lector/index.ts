// De archivos a modelo.
//
// El lector es puro: entra un mapa de ruta contra contenido, sale una Novela.
// No toca disco ni red. Es lo que permite que el servidor y el modo estatico
// produzcan el modelo con el mismo codigo, y lo que permite probarlo con las
// corridas reales que ya estan en books/.

import { leerContinuidad } from './continuidad.ts'
import { leerCuenta } from './cuenta.ts'
import { leerLuz, leerNombreDecision } from './luz.ts'
import { capitulosDePlan, tituloDePlan, vozDePlan } from './plan.ts'
import type {
  Archivos,
  Capitulo,
  EstadoCapitulo,
  EstadoNovela,
  Intento,
  Novela,
  Resumen,
} from './tipos.ts'

export * from './tipos.ts'
export { cuerpoDeLuz, leerLuz, leerNombreDecision } from './luz.ts'
export { leerModelosDeAgentes, rotuloDeModelo } from './cuenta.ts'
export type { ModeloDeAgente } from './cuenta.ts'
export { capitulosDePlan, tituloDePlan, vozDePlan } from './plan.ts'

function contarPalabras(texto: string): number {
  // El encabezado "# Capitulo N - Titulo" no es prosa del capitulo.
  const cuerpo = texto
    .replace(/^﻿/, '')
    .replace(/\r\n/g, '\n')
    .replace(/^#[^\n]*\n/, '')
    .trim()
  return cuerpo === '' ? 0 : cuerpo.split(/\s+/).length
}

function enCarpeta(archivos: Archivos, carpeta: string): [string, string][] {
  return Object.entries(archivos).filter(([ruta]) => ruta.startsWith(carpeta + '/'))
}

function nombreDe(ruta: string): string {
  return ruta.split('/').pop() ?? ''
}

export function leerNovela(slug: string, archivos: Archivos): Novela {
  const plan = archivos['plan.md'] ?? ''
  const capitulosPrevistos = capitulosDePlan(plan)
  const cierre = archivos['novela.md'] ?? null
  const cuenta = leerCuenta(archivos['sesion.json'])

  // --- los textos de los capitulos -------------------------------------
  const aprobados = new Map<number, string>()
  const borradores = new Map<number, string>()
  for (const [ruta, contenido] of enCarpeta(archivos, 'capitulos')) {
    const nombre = nombreDe(ruta)
    const borrador = nombre.match(/^(\d{2})\.borrador\.md$/)
    if (borrador) {
      borradores.set(Number(borrador[1]), contenido)
      continue
    }
    const aprobado = nombre.match(/^(\d{2})\.md$/)
    if (aprobado) aprobados.set(Number(aprobado[1]), contenido)
    // Cualquier otro nombre no entra: el nombre del archivo es el contrato.
  }

  // --- las luces, agrupadas por capitulo e intento ----------------------
  const porCapitulo = new Map<number, Map<number, Intento>>()
  for (const [ruta, contenido] of enCarpeta(archivos, 'decisiones')) {
    const partes = leerNombreDecision(nombreDe(ruta))
    if (!partes) continue
    if (!porCapitulo.has(partes.capitulo)) porCapitulo.set(partes.capitulo, new Map())
    const intentos = porCapitulo.get(partes.capitulo)!
    if (!intentos.has(partes.intento)) {
      intentos.set(partes.intento, { k: partes.intento, revisor: null, verificador: null })
    }
    const intento = intentos.get(partes.intento)!
    intento[partes.juez] = leerLuz(contenido, ruta, partes.juez)
  }

  // --- la continuidad ---------------------------------------------------
  const continuidades = new Map<number, ReturnType<typeof leerContinuidad>>()
  for (const [ruta, contenido] of enCarpeta(archivos, 'continuidad')) {
    const m = nombreDe(ruta).match(/^(\d{2})\.md$/)
    if (m) continuidades.set(Number(m[1]), leerContinuidad(contenido, ruta))
  }

  // --- el reparto de capitulos -----------------------------------------
  const numeros = new Set<number>([
    ...capitulosPrevistos.map((c) => c.numero),
    ...aprobados.keys(),
    ...borradores.keys(),
    ...porCapitulo.keys(),
  ])

  const capitulos: Capitulo[] = [...numeros]
    .sort((a, b) => a - b)
    .map((numero) => {
      const aprobado = aprobados.get(numero)
      const borrador = borradores.get(numero)
      const texto = aprobado ?? borrador ?? null
      const intentos = [...(porCapitulo.get(numero)?.values() ?? [])].sort((a, b) => a.k - b.k)

      let estado: EstadoCapitulo = 'pendiente'
      if (aprobado !== undefined) estado = 'aprobado'
      else if (borrador !== undefined || intentos.length > 0) estado = 'en curso'

      return {
        numero,
        estado,
        texto,
        esBorrador: aprobado === undefined && borrador !== undefined,
        palabras: texto ? contarPalabras(texto) : 0,
        intentos,
        continuidad: continuidades.get(numero) ?? null,
      }
    })

  // --- el estado de la novela ------------------------------------------
  //
  // El cierre manda: si hay novela.md, la novela esta terminada. Si no lo hay
  // pero hay un borrador, se esta escribiendo. Si no hay ninguna de las dos
  // cosas y faltan capitulos, esta parada: es el caso de control-07, que se
  // interrumpio a mano, y enseñarla como "en curso" seria decir que sigue.
  const hayBorrador = capitulos.some((c) => c.esBorrador)
  const aprobadosN = capitulos.filter((c) => c.estado === 'aprobado').length
  const previstosN = capitulosPrevistos.length

  let estado: EstadoNovela
  if (cierre !== null) estado = 'terminada'
  else if (hayBorrador) estado = 'en curso'
  else if (previstosN > 0 && aprobadosN >= previstosN) estado = 'terminada'
  else estado = 'parada'

  if (estado === 'parada') {
    for (const c of capitulos) if (c.estado === 'en curso') c.estado = 'parado'
  }

  return {
    slug,
    titulo: tituloDePlan(plan) || slug,
    voz: vozDePlan(plan),
    capitulosPrevistos,
    capitulos,
    cierre,
    cuenta,
    estado,
  }
}

export function resumenDeNovela(novela: Novela): Resumen {
  return {
    slug: novela.slug,
    titulo: novela.titulo,
    estado: novela.estado,
    capitulos: novela.capitulos.filter((c) => c.estado === 'aprobado').length,
    capitulosPrevistos: novela.capitulosPrevistos.length,
    intentos: intentosDe(novela),
    aLaPrimera: aLaPrimera(novela),
    costeUSD: novela.cuenta?.costeUSD ?? null,
  }
}

/** Cuantos intentos hubo en toda la novela. */
export function intentosDe(novela: Novela): number {
  return novela.capitulos.reduce((n, c) => n + c.intentos.length, 0)
}

/** Los capitulos que entraron al primer intento. */
export function aLaPrimera(novela: Novela): number {
  return novela.capitulos.filter((c) => c.estado === 'aprobado' && c.intentos.length === 1).length
}
