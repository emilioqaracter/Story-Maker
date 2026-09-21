// El lector de una luz. Las cuatro reglas del parser viven aqui y solo aqui.
//
// 1. La primera linea manda. Si no es exactamente "LUZ: VERDE" ni "LUZ: ROJA",
//    el veredicto es NO ENTENDIDA y se acabo. No se busca la palabra "verde"
//    mas abajo y no se adivina por el tono. Deducirlo seria decidir.
// 2. Los marcadores son literales, tal como los escribe la skill `luz`.
// 3. Lo que no case se ignora en silencio y sobrevive en `crudo`.
// 4. Todo se lee como UTF-8. De eso se encarga quien abre el archivo.

import type { Bloque, Juez, Luz, Veredicto } from './tipos.ts'

/** Sin tildes y en minusculas, solo para comparar nombres de marcador. */
function plano(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

function lineas(crudo: string): string[] {
  return crudo.replace(/^﻿/, '').replace(/\r\n/g, '\n').split('\n')
}

/** Regla 1. Exacta, sin interpretar. */
function veredictoDe(primera: string): Veredicto {
  const l = primera.trim()
  if (l === 'LUZ: VERDE') return 'VERDE'
  if (l === 'LUZ: ROJA') return 'ROJA'
  return 'NO ENTENDIDA'
}

const MARCADOR = /^\*\*\s*([^*:]+?)\s*:\s*\*\*\s*(.*)$/
const ENCABEZADO = /^##\s+(.*)$/

/**
 * El nombre de un marcador, normalizado.
 *
 * La skill `luz` los escribe sin tildes y asi estan en los 124 archivos de
 * decision que hay en books/, pero tres traen "Leccion" con tilde y dos traen
 * "Donde (borrador)" y "Donde (plan)". Se aceptan las dos formas y el
 * parentesis se descarta: el tablero tiene que leer lo que los jueces
 * escribieron, no lo que deberian haber escrito.
 */
function nombreDeMarcador(bruto: string): string {
  return plano(bruto)
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** El valor de un marcador llega hasta la linea en blanco siguiente. */
function juntarValor(ls: string[], desde: number, primera: string): { valor: string; siguiente: number } {
  const partes = [primera.trim()]
  let i = desde + 1
  while (i < ls.length) {
    const l = ls[i]
    if (l.trim() === '') break
    if (ENCABEZADO.test(l) || MARCADOR.test(l)) break
    partes.push(l.trim())
    i++
  }
  return { valor: partes.join(' ').trim(), siguiente: i }
}

function bloqueVacio(titulo: string): Bloque {
  return { titulo, donde: '', queCambiar: '' }
}

export function leerLuz(crudo: string, ruta: string, juez: Juez): Luz {
  const veredicto = veredictoDe(lineas(crudo)[0] ?? '')
  const luz: Luz = { juez, veredicto, bloques: [], refuerzo: null, leccion: null, crudo, ruta }

  // Una luz que no se entiende no se sigue leyendo: se ensena en crudo y se
  // marca. Sacarle bloques seria fingir que se entendio a medias.
  if (veredicto === 'NO ENTENDIDA') return luz

  const ls = lineas(crudo)
  const bloques: Bloque[] = []
  let bloque: Bloque | null = null
  let i = 1

  while (i < ls.length) {
    const linea = ls[i]

    const enc = linea.match(ENCABEZADO)
    if (enc) {
      if (bloque) bloques.push(bloque)
      bloque = bloqueVacio(enc[1].trim())
      i++
      continue
    }

    const marca = linea.match(MARCADOR)
    if (marca) {
      const nombre = nombreDeMarcador(marca[1])
      const { valor, siguiente } = juntarValor(ls, i, marca[2])
      i = siguiente
      if (nombre === 'donde') {
        if (!bloque) bloque = bloqueVacio('')
        bloque.donde = valor
      } else if (nombre === 'que cambiar') {
        if (!bloque) bloque = bloqueVacio('')
        bloque.queCambiar = valor
      } else if (nombre === 'leccion') {
        luz.leccion = valor
      } else if (nombre === 'refuerzo') {
        luz.refuerzo = valor
      }
      // Regla 3: cualquier otro marcador se ignora. Esta en crudo.
      continue
    }

    i++
  }

  if (bloque) bloques.push(bloque)
  luz.bloques = bloques
  return luz
}

/**
 * La prosa de la luz: lo que hay entre la primera linea y el primer marcador
 * de cierre. Es el motivo de una verde.
 *
 * No es un campo del modelo, es una derivacion de `crudo` para poder
 * ensenarlo. El texto sale del archivo tal cual: no se resume ni se reformula.
 */
export function cuerpoDeLuz(luz: Luz): string {
  const ls = lineas(luz.crudo).slice(1)
  const corte = ls.findIndex((l) => {
    const m = l.match(MARCADOR)
    if (!m) return false
    const n = nombreDeMarcador(m[1])
    return n === 'refuerzo' || n === 'leccion'
  })
  const cuerpo = corte === -1 ? ls : ls.slice(0, corte)
  return cuerpo.join('\n').trim()
}

const NOMBRE_DECISION = /^(\d{2})\.intento(\d+)\.(revisor|verificador)\.md$/

/**
 * El nombre del archivo es el contrato: capitulo, intento y juez sin abrirlo.
 * Devuelve null si el nombre no lo cumple, y entonces el archivo no entra en
 * el modelo: un archivo suelto en decisiones/ no puede inventar un intento.
 */
export function leerNombreDecision(
  nombre: string,
): { capitulo: number; intento: number; juez: Juez } | null {
  const m = nombre.match(NOMBRE_DECISION)
  if (!m) return null
  return { capitulo: Number(m[1]), intento: Number(m[2]), juez: m[3] as Juez }
}
