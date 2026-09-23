"""Los verificadores deterministas del texto.

RF-46 a RF-50. `architecture.md` §9.1. Corren **siempre antes que cualquier
juez**: coste despreciable y cero falsos positivos si estan bien escritos.

Todos devuelven defectos con **cita localizable**. Un defecto sin cita se
descarta, y ademas el Reparador necesita saber que arreglar, no que algo esta
mal.

Estos siete son la red de seguridad del sistema entero, y por eso son los unicos
a los que se les exige cobertura de mutacion: un verificador cuyas pruebas no
detectan su ruptura es **peor** que no tener verificador, porque produce
confianza falsa.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from commons.types.primitives import Defect, Evidence, Severity


def _cite(text: str, needle: str) -> Evidence:
    """Cita con su posicion. Si no se encuentra, cita el principio.

    Nunca devuelve una cita vacia: un defecto sin evidencia se descarta, asi que
    un verificador que no sepa citar seria un verificador que no sirve.
    """
    pos = text.find(needle)
    if pos < 0:
        return Evidence(quote=text[:80] or needle, offset=0)
    return Evidence(quote=needle, offset=pos)


def _normalize(word: str) -> str:
    """Minuscula y sin tildes, para comparar terminos.

    En espanol hace falta: "el Chino" y "el chino" son el mismo nombre para un
    lector y dos cadenas distintas para un `in`.
    """
    sin_tildes = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------ check.timeline

#: Solo nombres de mes: "marco 2 de los 3 penaltis" no es una fecha, y con
#: cualquier palabra detras del "de" el verificador daba S1 en prosa correcta.
_MONTHS = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    "septiembre|setiembre|octubre|noviembre|diciembre"
)
_DATE = re.compile(
    rf"\b(\d{{1,2}})\s+de\s+((?:{_MONTHS}|m[aá]rzo))\b|\b(\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)


def check_timeline(text: str, *, allowed_dates: Sequence[str]) -> list[Defect]:
    """Fechas mencionadas frente al calendario de la obra.

    Solo marca fechas en formato explicito: una fecha escrita en prosa
    --"el martes siguiente"-- no se puede contrastar sin entender el texto, y
    eso es trabajo del Continuista, no de un verificador determinista.
    """
    permitidas = {_normalize(d) for d in allowed_dates}
    out: list[Defect] = []
    for match in _DATE.finditer(text):
        mencion = match.group(0)
        if _normalize(mencion) not in permitidas:
            out.append(
                Defect(
                    kind="check.timeline",
                    severity=Severity.S1,
                    evidence=_cite(text, mencion),
                    rule=f"la fecha {mencion!r} no esta en el calendario de la obra",
                )
            )
    return out


# -------------------------------------------------------------- check.ledger


def check_ledger(text: str, *, expected_score: str, team_names: Sequence[str]) -> list[Defect]:
    """El marcador narrado cuadra con el que resolvio el motor de reglas.

    Marca **S1** toda cifra narrada que no cuadre: un marcador equivocado
    contradice el canon y rompe la clasificacion de toda la temporada, no es un
    matiz de estilo.
    """
    marcadores = re.findall(r"\b(\d{1,2})\s*[-a]\s*(\d{1,2})\b", text)
    esperado = tuple(expected_score.split("-"))
    out: list[Defect] = []
    for local, visitante in marcadores:
        if (local, visitante) != esperado:
            out.append(
                Defect(
                    kind="check.ledger",
                    severity=Severity.S1,
                    evidence=_cite(text, f"{local}-{visitante}"),
                    rule=f"el encuentro acabo {expected_score}, no {local}-{visitante}",
                )
            )
    return out


# -------------------------------------------------------- check.availability


def check_availability(text: str, *, unavailable: Sequence[tuple[str, str]]) -> list[Defect]:
    """Nadie actua estando indisponible en esa fecha (DEP-I2).

    `unavailable` son pares (nombre, motivo). Se pasa ya resuelto porque quien
    sabe quien estaba lesionado es el canon, y este modulo no abre la base.
    """
    plano = _normalize(text)
    return [
        Defect(
            kind="check.availability",
            severity=Severity.S1,
            evidence=_cite(text, nombre),
            rule=f"{nombre} esta {motivo} en esa fecha y no puede aparecer actuando",
        )
        for nombre, motivo in unavailable
        if _normalize(nombre) in plano
    ]


# -------------------------------------------------------------- check.format

_FIRST_PERSON = re.compile(r"\b(yo|me|mi|conmigo|nosotros|nuestro)\b", re.IGNORECASE)

#: Formas verbales frecuentes en narracion, en pasado y en presente.
#:
#: Se comparan LISTAS CERRADAS de verbos comunes en vez de intentar deducir el
#: tiempo por terminaciones. En espanol las terminaciones no separan: "mira" es
#: presente y "la puerta" acaba igual, asi que una regla por sufijo marcaria
#: sustantivos. Con verbos concretos el reconocimiento es exacto aunque no sea
#: exhaustivo, y para decidir en que tiempo esta una escena entera basta con
#: cual de los dos grupos domina.
_PAST_FORMS = frozenset(
    [
        "era",
        "eran",
        "estaba",
        "estaban",
        "habia",
        "habian",
        "tenia",
        "tenian",
        "fue",
        "fueron",
        "dijo",
        "dijeron",
        "miro",
        "miraron",
        "hizo",
        "hicieron",
        "vio",
        "vieron",
        "entro",
        "entraron",
        "salio",
        "salieron",
        "sintio",
        "sintieron",
        "supo",
        "supieron",
        "quiso",
        "quisieron",
        "pudo",
        "pudieron",
        "llego",
        "llegaron",
        "penso",
        "pensaron",
        "volvio",
        "volvieron",
        "paso",
        "pasaron",
        "dejo",
        "dejaron",
        "cogio",
        "cogieron",
    ]
)

_PRESENT_FORMS = frozenset(
    [
        "es",
        "son",
        "esta",
        "estan",
        "hay",
        "ha",
        "han",
        "tiene",
        "tienen",
        "va",
        "van",
        "dice",
        "dicen",
        "mira",
        "miran",
        "hace",
        "hacen",
        "ve",
        "ven",
        "entra",
        "entran",
        "sale",
        "salen",
        "siente",
        "sienten",
        "sabe",
        "saben",
        "quiere",
        "quieren",
        "puede",
        "pueden",
        "llega",
        "llegan",
        "piensa",
        "piensan",
        "vuelve",
        "vuelven",
        "pasa",
        "pasan",
        "deja",
        "dejan",
        "coge",
        "cogen",
    ]
)

#: Cuantas formas del tiempo equivocado hacen falta para marcar, y cuanto tiene
#: que dominar. Un pasaje en pasado puede llevar presentes legitimos --una
#: verdad general, un pensamiento-- asi que marcar al primero daria falsos
#: positivos en prosa correcta.
_TENSE_MIN_EVIDENCE = 4
_TENSE_RATIO = 2.0


def check_format(
    text: str,
    *,
    person: str = "tercera",
    tense: str = "pasado",
    word_range: tuple[int, int] | None = None,
) -> list[Defect]:
    """Persona, tiempo verbal y longitud.

    La longitud es S2 y no S1 a proposito: una escena larga de mas degrada el
    ritmo pero no contradice nada. La persona equivocada si es S1, porque rompe
    el punto de vista unico, que es una invariante estructural.
    """
    out: list[Defect] = []
    out += _check_tense(text, tense=tense)

    if person == "tercera":
        primera = _FIRST_PERSON.search(text)
        # El dialogo va en primera persona con toda naturalidad: solo se marca
        # fuera de comillas, o el verificador dispararia en cada conversacion.
        if primera and not _inside_quotes(text, primera.start()):
            out.append(
                Defect(
                    kind="check.format",
                    severity=Severity.S1,
                    evidence=_cite(text, primera.group(0)),
                    rule="la narracion es en tercera persona; esto esta en primera "
                    "y fuera de dialogo",
                )
            )

    if word_range is not None:
        palabras = len(text.split())
        low, high = word_range
        if not low <= palabras <= high:
            out.append(
                Defect(
                    kind="check.format",
                    severity=Severity.S2,
                    evidence=Evidence(quote=text[:80], offset=0),
                    rule=f"la escena tiene {palabras} palabras y el rango es {low}-{high}",
                )
            )
    return out


def check_chapter_length(text: str, *, word_range: tuple[int, int]) -> list[Defect]:
    """Longitud **escrita** de un capitulo frente a su rango (EST-07).

    La escaleta ya comprueba lo planificado; esto mide lo que de verdad se
    escribio, que es lo que lee el lector. Es la misma restriccion formal que
    `check.format` aplica a la escena (`architecture.md` §9.1), con la misma
    cuenta de palabras y la misma severidad: un capitulo largo o corto de mas
    degrada el ritmo, no contradice el canon. El rango lo pasa quien llama,
    porque sale de la escaleta y este modulo no importa de `planning/`.
    """
    palabras = len(text.split())
    low, high = word_range
    if low <= palabras <= high:
        return []
    return [
        Defect(
            kind="check.format",
            severity=Severity.S2,
            evidence=Evidence(quote=text[:80] or "(capitulo vacio)", offset=0),
            rule=f"el capitulo tiene {palabras} palabras y el rango es {low}-{high}",
        )
    ]


def _check_tense(text: str, *, tense: str) -> list[Defect]:
    """Tiempo verbal de la narracion.

    **Solo fuera de dialogo.** Los personajes hablan en presente con toda
    naturalidad aunque la narracion vaya en pasado; contar sus verbos haria que
    una escena con mucho dialogo se marcara siempre.

    Es **S1**: el tiempo verbal equivocado no es un matiz, rompe la guia de
    estilo en algo que un lector nota en la primera linea, y ademas afecta a la
    escena entera, no a un pasaje.

    Lo escribi sin esta comprobacion y la primera escena real que genero el
    sistema salio en presente sin que nada la marcara. De ahi que este aqui.
    """
    if tense != "pasado":
        return []

    narracion = [
        (m.group(0), m.start())
        for m in re.finditer(r"\w+", text)
        if not _inside_quotes(text, m.start())
    ]

    pasados = [w for w, _ in narracion if _normalize(w) in _PAST_FORMS]
    presentes = [(w, i) for w, i in narracion if _normalize(w) in _PRESENT_FORMS]

    if len(presentes) < _TENSE_MIN_EVIDENCE:
        return []
    if len(presentes) < max(1, len(pasados)) * _TENSE_RATIO:
        return []

    palabra, _pos = presentes[0]
    return [
        Defect(
            kind="check.format",
            severity=Severity.S1,
            evidence=_cite(text, palabra),
            rule=(
                f"la narracion va en presente y la guia pide pasado: "
                f"{len(presentes)} formas en presente frente a {len(pasados)} en pasado"
            ),
        )
    ]


def _inside_quotes(text: str, position: int) -> bool:
    """Si una posicion cae dentro de un dialogo.

    Cuenta las aperturas antes de esa posicion: en numero impar, esta dentro.
    Cubre comillas latinas, inglesas y raya de dialogo, que es como se escribe
    dialogo en espanol.
    """
    antes = text[:position]
    if antes.count("«") > antes.count("»"):
        return True
    if antes.count('"') % 2 == 1:
        return True
    ultima_linea = antes.rsplit("\n", 1)[-1]
    return ultima_linea.lstrip().startswith(("—", "-"))


# ---------------------------------------------------------- check.repetition


def check_repetition(
    text: str, *, frozen_ngrams: Sequence[str], proscribed: Sequence[str], n: int = 4
) -> list[Defect]:
    """N-gramas ya usados en prosa congelada, y terminos proscritos por estilo.

    Los dos son **S2**: repetir una imagen degrada la calidad sin contradecir
    nada. Marcarlos S1 pararia el capitulo por algo que el Estilista arregla en
    un pase.

    `proscribed` es solo el nivel `estilo` (POE-12, D-91). Las prohibidas del
    encargo --global, cliente, novela-- no pasan por aqui: son S1 de
    `check.forbidden` (`forbidden.py`, RF-236), y darlas tambien aqui como S2
    seria tener dos fuentes para el mismo termino.
    """
    out: list[Defect] = []
    palabras = [_normalize(w) for w in re.findall(r"\w+", text)]
    presentes = {" ".join(palabras[i : i + n]) for i in range(len(palabras) - n + 1)}

    for ngrama in frozen_ngrams:
        if _normalize(ngrama) in presentes:
            out.append(
                Defect(
                    kind="check.repetition",
                    severity=Severity.S2,
                    evidence=_cite(text, ngrama),
                    rule=f"la secuencia {ngrama!r} ya se uso en prosa congelada",
                )
            )

    plano = _normalize(text)
    out.extend(
        Defect(
            kind="check.repetition",
            severity=Severity.S2,
            evidence=_cite(text, termino),
            rule=f"{termino!r} esta en la lista de proscripcion",
        )
        for termino in proscribed
        if _normalize(termino) in plano
    )
    return out


# ------------------------------------------------------------- check.lexicon


def check_lexicon(
    text: str, *, known_names: Sequence[str], candidates: Sequence[str]
) -> list[Defect]:
    """Nombres propios que no estan en el canon.

    `candidates` son los nombres que aparecen en el texto, ya extraidos. Se pasa
    resuelto porque extraerlos bien exige analisis morfologico, y este modulo
    tiene que poder comprobarse sin dependencias pesadas.

    Un nombre vale solo si esta **exactamente** como en el canon, con sus tildes;
    la mayuscula no cuenta. Si no esta pero se queda a una edicion de uno que si
    --"Nalah" o "Nála" frente a "Nala"--, el defecto lo dice: al Reparador le
    sirve saber que es una errata del nombre y no un personaje que sobra.
    """
    exactos = {n.casefold() for n in known_names}
    out: list[Defect] = []
    for nombre in candidates:
        if nombre.casefold() in exactos:
            continue
        origen = misspelling_of(nombre, known_names)
        regla = (
            f"{nombre!r} es una variante mal escrita de {origen!r}, nombre del canon"
            if origen is not None
            else f"{nombre!r} no es una entidad del canon ni un alias vigente"
        )
        out.append(
            Defect(
                kind="check.lexicon",
                severity=Severity.S1,
                evidence=_cite(text, nombre),
                rule=regla,
            )
        )
    return out


def edit_distance(a: str, b: str) -> int:
    """Distancia de Damerau-Levenshtein restringida (alineamiento optimo).

    Cuenta insercion, borrado, sustitucion y trasposicion de dos letras
    contiguas, que son las cuatro erratas de teclado. Una tilde cambiada es una
    sustitucion: "a" y "á" son letras distintas.
    """
    prev2: list[int] = []
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            coste = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + coste)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[len(b)]


def misspelling_of(word: str, known_names: Sequence[str]) -> str | None:
    """El nombre del canon del que `word` es una errata, o `None`.

    Errata es estar a una edicion de un nombre del canon (`edit_distance` 1,
    con tildes) o ser igual a el salvo tildes. Solo cuentan los nombres que
    empiezan en mayuscula: el "el" de "el Chino" es un articulo, no un nombre,
    y sin este filtro "Del" seria su errata. Un nombre que ya esta en el canon
    no es errata de nada, aunque se parezca a otro.
    """
    w = word.casefold()
    if any(w == n.casefold() for n in known_names):
        return None
    for nombre in sorted(n for n in known_names if n[:1].isupper()):
        k = nombre.casefold()
        if _normalize(w) == _normalize(k) or edit_distance(w, k) == 1:
            return nombre
    return None


# ----------------------------------------------------------- check.knowledge


def check_knowledge(
    text: str, *, pov_knows: Sequence[str], mentioned_facts: Sequence[tuple[str, str]]
) -> list[Defect]:
    """Menciones de hechos que el POV todavia no conoce (PER-I1).

    `mentioned_facts` son pares (clave del hecho, cita en el texto), ya
    extraidos. **S1 siempre**: que un personaje sepa algo que no puede saber no
    es un desliz de estilo, es una contradiccion del canon, y ademas de las que
    un lector detecta.
    """
    sabe = set(pov_knows)
    return [
        Defect(
            kind="check.knowledge",
            severity=Severity.S1,
            evidence=_cite(text, cita),
            rule=f"el POV no conoce {clave!r} en este instante",
        )
        for clave, cita in mentioned_facts
        if clave not in sabe
    ]


# ---------------------------------------------------------- check.milestones


def check_milestones(text: str, *, scorers: Sequence[str]) -> list[Defect]:
    """Todo goleador de la cronologia aparece en la prosa (RF-44).

    Complementa a `check.ledger`: aquel comprueba que el marcador narrado cuadre;
    este, que la prosa cuente los hitos que el motor de reglas decidio. Un gol
    que la cronologia registra y la prosa omite es **S1**: el lector y la
    clasificacion dejan de contar lo mismo.
    """
    plano = _normalize(text)
    return [
        Defect(
            kind="check.ledger",
            severity=Severity.S1,
            evidence=Evidence(quote=text[:80] or nombre, offset=0),
            rule=f"la cronologia registra un gol de {nombre} y la prosa no lo cuenta",
        )
        for nombre in scorers
        if _normalize(nombre) not in plano
    ]
