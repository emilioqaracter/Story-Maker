// De continuidad/NN.md salen los hechos que un capitulo deja fijados.
//
// Es lo que el verificador anoto al dar la verde, y es lo ultimo que se lee en
// la vista del expediente: lo que a partir de aqui ya no se puede contradecir.

import type { Continuidad } from './tipos.ts'

function plano(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

function lineas(crudo: string): string[] {
  return crudo.replace(/^﻿/, '').replace(/\r\n/g, '\n').split('\n')
}

/** Las secciones de nivel 2, por su nombre sin tildes. */
function secciones(crudo: string): Map<string, string[]> {
  const mapa = new Map<string, string[]>()
  let actual: string | null = null
  for (const l of lineas(crudo)) {
    const enc = l.match(/^##\s+(.*)$/)
    if (enc && !l.startsWith('###')) {
      actual = plano(enc[1])
      mapa.set(actual, [])
      continue
    }
    if (actual) mapa.get(actual)!.push(l)
  }
  return mapa
}

function prosa(ls: string[] | undefined): string {
  return (ls ?? []).join('\n').trim()
}

/**
 * Las vinetas de una seccion.
 *
 * Una vineta partida en varias lineas del Markdown sigue siendo una vineta:
 * las continuaciones se pegan a la de arriba. Quedarse solo con la linea que
 * empieza por el guion corta los hechos a media frase, y un hecho a medias en
 * el expediente es peor que no enseñarlo, porque parece completo.
 */
function vinetas(ls: string[] | undefined): string[] {
  const salida: string[] = []
  let actual: string | null = null

  const cerrar = () => {
    if (actual !== null && actual.trim() !== '') salida.push(actual.trim())
    actual = null
  }

  for (const l of ls ?? []) {
    const abre = l.match(/^\s*[-*·]\s+(.*)$/)
    if (abre) {
      cerrar()
      actual = abre[1]
      continue
    }
    if (l.trim() === '') {
      cerrar()
      continue
    }
    if (actual !== null) actual += ` ${l.trim()}`
  }
  cerrar()
  return salida
}

/**
 * Busca una seccion por como empieza su nombre, no por como es exactamente:
 * los titulos varian entre novelas y el encabezado no es un contrato como si
 * lo es el nombre del archivo.
 */
function buscar(mapa: Map<string, string[]>, ...prefijos: string[]): string[] | undefined {
  for (const [nombre, contenido] of mapa) {
    if (prefijos.some((p) => nombre.startsWith(plano(p)))) return contenido
  }
  return undefined
}

export function leerContinuidad(crudo: string, ruta: string): Continuidad {
  const mapa = secciones(crudo)
  const primera = lineas(crudo).find((l) => l.trim() !== '') ?? ''
  return {
    titulo: primera.replace(/^#+\s*/, '').trim(),
    cuandoYDonde: prosa(buscar(mapa, 'cuando y donde')),
    hechos: vinetas(buscar(mapa, 'hechos que quedan fijados', 'hechos')),
    dondeTermina: prosa(buscar(mapa, 'donde termina')),
    noRepetir: vinetas(buscar(mapa, 'imagenes y escenas que no deberian repetirse', 'imagenes')),
    crudo,
    ruta,
  }
}
