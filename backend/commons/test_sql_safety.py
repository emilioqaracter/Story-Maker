"""Ninguna consulta interpola datos.

RD-11. Sustituye a la comprobacion generica del escaner de seguridad, que aqui
no servia: marca **toda** consulta construida con f-string, y en este backend
son legitimas --se interpolan marcadores `?` y nombres de tabla constantes--
pero las sentencias multilinea hacen que la supresion por linea sea imposible de
colocar bien. Lo intente dos veces y las dos veces el comentario acabo dentro de
la cadena SQL, rompiendo la consulta.

Asi que la reemplazo por una mas afilada. En vez de "esta consulta usa
f-string", que es cierto y no dice nada, esta comprueba **que se interpola**:
cada nombre que aparece entre llaves en una consulta tiene que estar en la lista
de abajo, con su motivo. Un nombre nuevo falla hasta que alguien lo anada, que
es justo la revision que hace falta.

Es mas estricta que la generica, no menos: la generica se silencia por linea y
se olvida; esta obliga a declarar cada caso en un solo sitio visible.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

#: Lo que se puede interpolar en una consulta, y por que.
#:
#: Todos son o marcadores de posicion generados con `?`, o constantes de su
#: propio modulo. **Ningun dato de usuario, de modelo o de la base.**
SAFE_INTERPOLATIONS = {
    # Cadenas de marcadores: ",".join("?" * n) o ",".join(["(?)"] * n)
    "marks": "marcadores ? generados por numero de parametros",
    "placeholders": "idem",
    "seed_values": "idem, para VALUES de un CTE",
    # Fragmentos SQL constantes del modulo
    "_COLUMNS": "lista de columnas, constante del modulo",
    "_ORDER": "clausula ORDER BY, constante del modulo",
    "_ALIVE": "predicado de vigencia, constante del modulo",
    "clause": "predicado armado solo con marcadores, en _filter_clause",
    # Nombres de tabla de tuplas constantes
    "table": "nombre de tabla, de PROJECTED_TABLES",
    "tabla": "nombre de tabla, de una tupla literal del modulo",
    "where": "predicado constante, de las llamadas internas de _close_open",
}

#: Palabras que delatan que una cadena es SQL.
_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|WITH RECURSIVE)\b", re.IGNORECASE)

_ROOT = Path(__file__).resolve().parent.parent


def _sql_interpolations() -> list[tuple[str, int, str]]:
    """Todos los nombres interpolados en cadenas SQL del backend."""
    hallazgos: list[tuple[str, int, str]] = []

    for ruta in _ROOT.rglob("*.py"):
        if "test_" in ruta.name:
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))

        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.JoinedStr):
                continue
            # `ast.Constant.value` puede ser de cualquier tipo; en una f-string
            # las partes literales son siempre texto, pero el tipo no lo sabe.
            literal = "".join(
                p.value
                for p in nodo.values
                if isinstance(p, ast.Constant) and isinstance(p.value, str)
            )
            if not _SQL.search(literal):
                continue
            for parte in nodo.values:
                if isinstance(parte, ast.FormattedValue):
                    nombre = ast.unparse(parte.value)
                    hallazgos.append((str(ruta.relative_to(_ROOT)), nodo.lineno, nombre))
    return hallazgos


def test_toda_interpolacion_en_sql_esta_declarada() -> None:
    """Un nombre nuevo en una consulta falla hasta que se declare aqui."""
    sin_declarar = [
        f"{fichero}:{linea} interpola {nombre!r}"
        for fichero, linea, nombre in _sql_interpolations()
        if nombre not in SAFE_INTERPOLATIONS
    ]
    assert not sin_declarar, (
        "interpolaciones sin declarar en SAFE_INTERPOLATIONS:\n  "
        + "\n  ".join(sin_declarar)
        + "\n\nSi es un marcador o una constante del modulo, anadelo con su motivo. "
        "Si es un dato, NO se interpola: va como parametro."
    )


def test_hay_consultas_que_revisar() -> None:
    """La comprobacion anterior seria trivial si no encontrara ninguna consulta.

    Un fallo del analisis --un cambio de version de `ast`, un renombrado de
    carpetas-- la dejaria pasando sin mirar nada, que es la forma en que una
    comprobacion deja de proteger sin que nadie se entere.
    """
    assert len(_sql_interpolations()) >= 10


def test_ninguna_consulta_concatena_con_mas() -> None:
    """RD-11. Ningun valor va concatenado; todo va como parametro.

    La concatenacion con `+` sobre una cadena SQL es la forma clasica del
    problema, y a diferencia del f-string no tiene ningun uso legitimo aqui.
    """
    malos: list[str] = []
    for ruta in _ROOT.rglob("*.py"):
        if "test_" in ruta.name:
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.BinOp)
                and isinstance(nodo.op, ast.Add)
                and isinstance(nodo.left, ast.Constant)
                and isinstance(nodo.left.value, str)
                and _SQL.search(nodo.left.value)
                and not isinstance(nodo.right, ast.Constant)
            ):
                malos.append(f"{ruta.relative_to(_ROOT)}:{nodo.lineno}")
    assert not malos, f"SQL concatenado con un valor: {malos}"
