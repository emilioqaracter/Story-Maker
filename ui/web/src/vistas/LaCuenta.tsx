// Lo que costo, y donde se fue.
//
// El argumento de esta pantalla es uno solo: el dinero se va en los dos
// agentes que deciden, no en los que ejecutan. Eso no es un accidente, esta en
// la spec y se puede leer en los numeros.
//
// Y de donde salen: de sesion.json, que Claude Code deja en la carpeta de la
// novela. No se estima nada y no se llama a ninguna API. Lo que falta, se dice
// que falta.

import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import { duracion, entero, miles, SIN_MEDIR, usd, usdOSinMedir } from '../diseno/formato.ts'
import { rotuloDeModelo } from '../lector/index.ts'
import type { ModeloDeAgente, Novela, Resumen } from '../lector/index.ts'

export function LaCuenta({
  novela,
  resumenes,
  agentes,
}: {
  novela: Novela
  resumenes: Resumen[]
  agentes: ModeloDeAgente[]
}) {
  const cuenta = novela.cuenta

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-7 px-12 py-8">
      <Titulares cuenta={cuenta} />

      <section className="shrink-0">
        <Rotulo>Dónde se fue el dinero</Rotulo>
        {cuenta ? (
          <Dinero cuenta={cuenta} agentes={agentes} />
        ) : (
          <SinMedir slug={novela.slug} />
        )}
      </section>

      <div className="flex min-h-0 flex-1 gap-12">
        <section className="w-64 shrink-0">
          <Rotulo>Quién trabajó</Rotulo>
          {cuenta && cuenta.despachos.length > 0 ? (
            <ul className="mt-2 space-y-1">
              {cuenta.despachos.map((d) => (
                <li
                  key={d.tipo}
                  className="flex justify-between font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave"
                >
                  <span>{d.tipo}</span>
                  <span className="tabular-nums text-texto">{d.n}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
              {SIN_MEDIR}
            </p>
          )}
        </section>

        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <Rotulo>Todas las corridas</Rotulo>
          <div className="min-h-0 flex-1">
            <Corridas resumenes={resumenes} actual={novela.slug} />
          </div>
        </section>
      </div>
    </div>
  )
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-[family-name:var(--font-maquina)] text-[11px] tracking-[0.14em] text-texto-suave">
      {children}
    </p>
  )
}

function Titulares({ cuenta }: { cuenta: Novela['cuenta'] }) {
  const celdas: [string, string][] = cuenta
    ? [
        [usd(cuenta.costeUSD), 'coste medido'],
        [duracion(cuenta.duracionMs), 'de reloj'],
        [entero(cuenta.subagentes), 'subagentes'],
        [entero(cuenta.fallos), cuenta.fallos === 1 ? 'fallo' : 'fallos'],
      ]
    : [[SIN_MEDIR, 'esta novela no tiene sesion.json']]

  return (
    <div className="flex shrink-0 gap-16">
      {celdas.map(([valor, pie]) => (
        <div key={pie}>
          <p className="font-[family-name:var(--font-maquina)] text-[30px] leading-none tabular-nums text-texto">
            {valor}
          </p>
          <p className="mt-2 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
            {pie}
          </p>
        </div>
      ))}
    </div>
  )
}

/**
 * Una barra por modelo, y el rotulo de que hace cada uno.
 *
 * El rotulo no esta escrito a mano: sale del frontmatter de .claude/agents, que
 * es donde vive de verdad que modelo usa cada agente. El dia que el revisor
 * cambie de modelo, esta pantalla lo cuenta sola. Y si ningun agente declara
 * un modelo, va sin rotulo en vez de con uno adivinado.
 */
function Dinero({
  cuenta,
  agentes,
}: {
  cuenta: NonNullable<Novela['cuenta']>
  agentes: ModeloDeAgente[]
}) {
  const datos = cuenta.modelos.map((m) => ({
    ...m,
    corto: m.modelo.replace(/^claude-/, '').replace(/-\d{8}$/, ''),
    rotulo: rotuloDeModelo(m.modelo, agentes),
  }))
  const caro = datos[0]?.modelo
  // Una franja por modelo, y la altura sale de cuantos hay. Con alto libre,
  // dos barras se reparten media pantalla y el grafico deja de leerse como una
  // comparacion para leerse como un adorno.
  const ALTO_FILA = 54

  return (
    <div className="mt-3 flex gap-8" style={{ height: datos.length * ALTO_FILA }}>
      <div className="min-w-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={datos}
            layout="vertical"
            barCategoryGap="28%"
            margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
          >
            <XAxis type="number" hide domain={[0, 'dataMax']} />
            <YAxis type="category" dataKey="corto" hide />
            <Bar dataKey="costeUSD" radius={2} isAnimationActive={false}>
              {datos.map((d) => (
                <Cell
                  key={d.modelo}
                  // El naranja marca donde se fue el dinero, que es el unico
                  // punto de esta pantalla. Los demas van en gris.
                  fill={d.modelo === caro ? 'var(--color-naranja)' : 'var(--color-borde)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul className="flex w-[26rem] shrink-0 flex-col">
        {datos.map((d) => (
          <li
            key={d.modelo}
            className="flex flex-col justify-center font-[family-name:var(--font-maquina)] text-[12px]"
            style={{ height: ALTO_FILA }}
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-texto">{d.corto}</span>
              <span className="tabular-nums text-texto">{usd(d.costeUSD)}</span>
            </div>
            <div className="flex items-baseline justify-between gap-3 text-[11px] text-texto-suave">
              <span>{d.rotulo ?? 'sin agente que lo declare'}</span>
              <span className="tabular-nums">
                {miles(d.entrada)} ent · {miles(d.salida)} sal · {miles(d.razonamiento)} razón
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SinMedir({ slug }: { slug: string }) {
  return (
    <div className="mt-3 rounded-sm border border-dashed border-borde p-6">
      <p className="font-[family-name:var(--font-maquina)] text-[12px] text-texto-suave">
        <span className="text-texto">{slug}</span> no tiene <span className="text-texto">sesion.json</span>,
        así que su coste está <span className="text-texto">sin medir</span>.
      </p>
      <p className="mt-2 font-[family-name:var(--font-maquina)] text-[11px] text-texto-suave">
        No hay un cero ni una estimación en su sitio. Un número inventado en esta pantalla se lleva
        por delante la credibilidad de las otras dos.
      </p>
    </div>
  )
}

function Corridas({ resumenes, actual }: { resumenes: Resumen[]; actual: string }) {
  return (
    <div className="mt-2 h-full overflow-y-auto pr-2">
      <table className="w-full font-[family-name:var(--font-maquina)] text-[12px]">
        <thead>
          <tr className="text-[10px] tracking-wide text-texto-suave">
            <th className="pb-1 text-left font-normal">novela</th>
            <th className="pb-1 text-right font-normal">coste</th>
            <th className="pb-1 text-right font-normal">caps</th>
            <th className="pb-1 text-right font-normal">intentos</th>
            <th className="pb-1 text-right font-normal">a la primera</th>
          </tr>
        </thead>
        <tbody>
          {resumenes.map((r) => (
            <tr
              key={r.slug}
              className={r.slug === actual ? 'text-texto' : 'text-texto-suave'}
            >
              <td className="py-[3px]">{r.slug}</td>
              <td className="py-[3px] text-right tabular-nums">{usdOSinMedir(r.costeUSD)}</td>
              <td className="py-[3px] text-right tabular-nums">
                {r.capitulos}
                <span className="text-texto-suave">/{r.capitulosPrevistos}</span>
              </td>
              <td className="py-[3px] text-right tabular-nums">{r.intentos}</td>
              <td className="py-[3px] text-right tabular-nums">{r.aLaPrimera}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
