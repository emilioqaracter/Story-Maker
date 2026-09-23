/**
 * Fallo de red (RF-164). Ofrece repetir la **lectura**: es un `GET` y no toca el
 * ciclo. No es «reintentar la tirada», que no existe en ninguna pantalla (RF-199).
 */
export function NetworkError({ reload }: { reload: () => void }) {
  return (
    <section className="notice" role="alert">
      <h2>No se pudo hablar con el backend</h2>
      <p>Comprueba que el backend está en marcha en esta misma máquina.</p>
      <button type="button" onClick={reload}>
        Volver a cargar
      </button>
    </section>
  );
}
