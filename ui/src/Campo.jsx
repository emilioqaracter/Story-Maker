/**
 * Un campo del formulario. El ejemplo va DEBAJO y siempre: es lo que convierte
 * "que los separa" en una pregunta que se puede contestar sin adivinar el tono.
 * La nota explica por que se pide el dato, que es distinto de como llenarlo.
 */
export default function Campo({
  etiqueta,
  ejemplo,
  nota,
  ancho = false,
  destacado = false,
  filas = 0,
  tipo = 'text',
  valor,
  onChange,
  children,
}) {
  const clases = ['campo', ancho && 'ancho', destacado && 'destacado']
    .filter(Boolean)
    .join(' ')

  return (
    <label className={clases}>
      <span className="etiqueta">{etiqueta}</span>

      {children ? (
        children
      ) : filas ? (
        <textarea rows={filas} value={valor} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input type={tipo} value={valor} onChange={(e) => onChange(e.target.value)} />
      )}

      {ejemplo && (
        <span className="ejemplo">
          <span className="ej">ej</span>
          {ejemplo}
        </span>
      )}
      {nota && <span className="nota">{nota}</span>}
    </label>
  )
}
