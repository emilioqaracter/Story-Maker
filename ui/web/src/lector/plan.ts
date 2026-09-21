// De plan.md salen el titulo, la voz y los capitulos previstos.

import type { CapPlan } from './tipos.ts'

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

/** La primera linea del plan, sin la almohadilla. */
export function tituloDePlan(plan: string): string {
  for (const l of lineas(plan)) {
    if (l.trim() === '') continue
    return l.replace(/^#+\s*/, '').trim()
  }
  return ''
}

/**
 * Una seccion de nivel 2, hasta el siguiente "## ". Los "### " de dentro no
 * la cortan: son sus capitulos.
 */
function seccion(plan: string, nombre: string): string {
  const ls = lineas(plan)
  const buscado = plano(nombre)
  let dentro = false
  const trozo: string[] = []
  for (const l of ls) {
    const enc = l.match(/^##\s+(.*)$/)
    if (enc && !l.startsWith('###')) {
      if (dentro) break
      if (plano(enc[1]) === buscado) dentro = true
      continue
    }
    if (dentro) trozo.push(l)
  }
  return trozo.join('\n').trim()
}

export function vozDePlan(plan: string): string {
  return seccion(plan, 'La voz')
}

const ENCABEZADO_CAP = /^###\s+Cap[ií]tulo\s+(\d+)\s*[-–—]\s*(.*)$/i

/**
 * "### Capitulo 1 - El sueno roto - 500 palabras - introduccion".
 *
 * Los tres trozos de detras del titulo se leen por lo que son y no por su
 * posicion: el que dice "N palabras" son las palabras y el otro es la parte.
 * Un plan que no traiga alguno deja el campo en null, no en cero.
 */
export function capitulosDePlan(plan: string): CapPlan[] {
  const previstos: CapPlan[] = []
  for (const l of lineas(plan)) {
    const m = l.match(ENCABEZADO_CAP)
    if (!m) continue
    const partes = m[2].split(/\s+[-–—]\s+/)
    let palabras: number | null = null
    let parte: string | null = null
    for (const p of partes.slice(1)) {
      const mp = p.trim().match(/^(\d+)\s*palabras$/i)
      if (mp) palabras = Number(mp[1])
      else if (p.trim() !== '') parte = p.trim()
    }
    previstos.push({
      numero: Number(m[1]),
      titulo: (partes[0] ?? '').trim(),
      palabras,
      parte,
    })
  }
  return previstos.sort((a, b) => a.numero - b.numero)
}
