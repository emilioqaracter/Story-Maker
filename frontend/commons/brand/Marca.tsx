// El logo de la empresa, traido de la rama main (ui/web/src/diseno/Marca.tsx).
// Alli las clases eran de Tailwind; aqui van en `style`, porque este frontend
// no lo usa. Lo monta la cabecera (commons/shell/Layout.tsx): las reglas de uso estan en BRAND.md.
//
// Se usa solo la version negativa -isotipo naranja y logotipo en blanco puro-,
// que es la que entrego la empresa y la unica que hay. No se recolorea, no se
// estira y no se recorta: no es un elemento de la interfaz, es un archivo de
// otra persona.
//
// Los dos naranjas no se unifican: el PNG trae el isotipo en #FF7932 y la
// paleta dice #F4631E. El del archivo es el logo; el de la paleta es la
// interfaz. Retocar el PNG para que casen seria editar la marca de la empresa.

import logo from "./logo-negativo.png";

export function Marca({ alto = 24 }: { alto?: number }) {
  return (
    <img
      src={logo}
      alt="Qaracter"
      // El margen libre a los lados es igual a la altura del isotipo: pegado a
      // un borde no se lee.
      style={{
        height: alto,
        marginInline: alto,
        width: "auto",
        display: "block",
        flexShrink: 0,
        userSelect: "none",
      }}
      draggable={false}
    />
  );
}
