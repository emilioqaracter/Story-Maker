// El manuscrito: prosa con tipografia de libro sobre el papel corporativo.
//
// Aqui no entra el logo. La prosa la escribio un agente, no la empresa, y
// firmar un capitulo con la marca mezcla quien lo escribio con quien lo
// ensena, que es la distincion de la que viven todas las vistas.
//
// Sirve para un capitulo y para la novela entera: la unica diferencia es que
// novela.md trae varios encabezados, uno por capitulo, y el primero es el
// titulo del libro.

import { entero } from '../diseno/formato.ts'
import type { Capitulo } from '../lector/index.ts'

type Bloque = { encabezado: string | null; parrafos: string[] }

function bloquesDe(texto: string): Bloque[] {
  const bloques: Bloque[] = []
  let actual: Bloque | null = null

  for (const trozo of texto.replace(/\r\n/g, '\n').split(/\n{2,}/)) {
    const t = trozo.trim()
    if (t === '') continue
    if (t.startsWith('#')) {
      actual = { encabezado: t.replace(/^#+\s*/, ''), parrafos: [] }
      bloques.push(actual)
      continue
    }
    if (!actual) {
      actual = { encabezado: null, parrafos: [] }
      bloques.push(actual)
    }
    actual.parrafos.push(t)
  }
  return bloques
}

function contarPalabras(texto: string): number {
  const cuerpo = texto.replace(/^#[^\n]*$/gm, '').trim()
  return cuerpo === '' ? 0 : cuerpo.split(/\s+/).length
}

export function Papel({
  texto,
  capitulo,
  esNovela = false,
  pie,
}: {
  texto: string | null
  capitulo?: Capitulo | null
  esNovela?: boolean
  /** Lo que va a la derecha del pie: la navegacion, normalmente. */
  pie?: React.ReactNode
}) {
  if (texto === null) {
    return (
      <section className="flex min-h-0 flex-1 flex-col items-center justify-center bg-papel">
        <p className="font-[family-name:var(--font-maquina)] text-[12px] text-tinta-suave">
          este capítulo todavía no está escrito
        </p>
      </section>
    )
  }

  const bloques = bloquesDe(texto)
  const palabras = capitulo ? capitulo.palabras : contarPalabras(texto)

  return (
    <section className="flex min-h-0 flex-1 flex-col bg-papel text-tinta">
      <div className="min-h-0 flex-1 overflow-y-auto px-12 py-8">
        {bloques.map((b, i) => (
          <div key={i}>
            {b.encabezado && (
              <>
                <h2
                  className={
                    'font-[family-name:var(--font-libro)] font-semibold ' +
                    (i === 0 ? (esNovela ? 'text-[28px]' : 'text-[22px]') : 'mt-10 text-[20px]')
                  }
                >
                  {b.encabezado}
                </h2>
                <div className="mt-2 mb-6 h-px w-24 bg-tinta-suave/40" />
              </>
            )}
            {b.parrafos.map((p, k) => (
              <p
                key={k}
                className="mb-4 font-[family-name:var(--font-libro)] text-[16px] leading-[1.7]"
              >
                {p}
              </p>
            ))}
          </div>
        ))}
      </div>

      <div className="flex shrink-0 items-center justify-between gap-6 border-t border-tinta-suave/20 px-12 py-4 font-[family-name:var(--font-maquina)] text-[11px] text-tinta-suave">
        <span>
          [ {entero(palabras)} palabras
          {capitulo
            ? ` · ${capitulo.intentos.length} ${capitulo.intentos.length === 1 ? 'intento' : 'intentos'}`
            : ''}
          {capitulo?.esBorrador ? ' · borrador' : ''}
          {esNovela ? ' · novela.md' : ''} ]
        </span>
        {pie}
      </div>
    </section>
  )
}
