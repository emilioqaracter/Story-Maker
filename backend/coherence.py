#!/usr/bin/env python
"""El ciclo docs -> spec -> plan, hecho codigo. `AGENTS.md` 6.7.

Tres niveles de documento describen un solo sistema desde tres alturas:
`docs/` dice que es, `specs/` que hace cada paso, `backend/PLAN.md` y
`frontend/PLAN.md` en que orden se construye. Se desalinean en silencio si nadie los contrasta, y una
revision "cuando toque" es la forma conocida de no contrastarlos. Asi que el
contraste corre en la puerta, en cada cambio, y falla si encuentra:

- un identificador citado que no existe, o definido dos veces;
- un requisito sin metodo `VER-NN`, o con uno que no existe;
- una seccion citada de `architecture.md`, `verification.md` o `AGENTS.md`
  que no existe;
- un requisito fuera de la matriz requisito x metodo de su SRS;
- un requisito que ningun tramo construye;
- una seccion de `architecture.md` sin fila en la matriz de cobertura del plan;
- un paquete de `backend/` o una carpeta de `frontend/` que el reparto fisico no declara;
- un requisito del frontend en un tramo del plan distinto del que le da su SRS;
- un numero de tramo definido dos veces;
- un `kind` `check.*` del codigo sin fila en la tabla de validadores de
  `architecture.md` §9.1, una fila que nombra un `check.*` que no existe, una
  fila sin punto de ejecucion, o una tabla por brief (`evals/brief_table.py`)
  sin columna fija para un verificador de escena de esa tabla (RF-268).

No comprueba que lo escrito sea verdad. Comprueba que los tres documentos
hablan de las mismas cosas con los mismos nombres, que es la condicion para
que alguien pueda comprobar lo demas.

    python coherence.py          # desde backend/
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
#: Todas las specs de la carpeta: los IDs son unicos en `specs/` entera (`AGENTS.md` §3.3),
#: no solo entre las del backend.
SPECS = sorted((ROOT / "specs").glob("srs-*-v*.md"))
PLAN = ROOT / "backend" / "PLAN.md"
FRONTEND_PLAN = ROOT / "frontend" / "PLAN.md"
FRONTEND_SPEC = ROOT / "specs" / "srs-frontend-v1.md"
AGENTS = ROOT / "AGENTS.md"
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

REQ_FAMILIES = ("RF", "RD", "RI", "RNF")
REQ_RE = re.compile(r"\b(RF|RD|RI|RNF)-(\d{2,3})\b")
DEC_RE = re.compile(r"\bD-(\d{2,3})\b")
VER_RE = re.compile(r"\bVER-(\d{2})\b")
DOM_RE = re.compile(r"\b(MET|EST|PER|MUN|DEP|POE|CAN|CTX|CAL|PRO)-(\d{2}|I\d)\b")
SEC_RE = re.compile(r"§(\d+(?:\.\d+)?)")
RANGE_RE = re.compile(r"\b(RF|RD|RI|RNF)-(\d{2,3}) a (?:RF|RD|RI|RNF)-(\d{2,3})\b")
SEC_RANGE_RE = re.compile(r"§(\d+)\.(\d+) a §(\d+)\.(\d+)")
TRAMO_RE = re.compile(r"\bT(\d{1,2})\b")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def headings(text: str) -> set[str]:
    """Numeros de seccion `N` y `N.N` de un documento markdown."""
    found: set[str] = set()
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(\d+(?:\.\d+)?)[\s.]", line)
        if m:
            found.add(m.group(1))
    return found


def expand_reqs(text: str) -> set[str]:
    """Todos los IDs de requisito de un texto, con los rangos `RF-03 a RF-09` expandidos."""
    ids = {f"{f}-{n}" for f, n in REQ_RE.findall(text)}
    for fam, a, b in RANGE_RE.findall(text):
        width = len(a)
        for n in range(int(a), int(b) + 1):
            ids.add(f"{fam}-{n:0{width}d}")
    return ids


def defined_reqs(spec: str) -> dict[str, str]:
    """ID -> fila donde se define. Una definicion es una fila de tabla `| RF-NN |` o un `- **RI-NN**`."""
    out: dict[str, str] = {}
    for line in spec.splitlines():
        m = re.match(r"^\|\s*((?:RF|RD|RI|RNF)-\d{2,3})\s*\|", line)
        if m:
            out[m.group(1)] = line
            continue
        m = re.match(r"^-\s+\*\*((?:RF|RD|RI|RNF)-\d{2,3})\*\*", line)
        if m:
            out[m.group(1)] = line
    return out


def defined_decisions(spec: str) -> set[str]:
    return {
        m.group(1) for line in spec.splitlines() if (m := re.match(r"^\|\s*(D-\d{2,3})\s*\|", line))
    }


def section(text: str, title_prefix: str) -> str:
    """Texto de la seccion cuyo encabezado empieza por `title_prefix`, hasta el siguiente del mismo nivel o superior."""
    lines = text.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3})\s+(.*)", line)
        if m and m.group(2).startswith(title_prefix):
            start, level = i, len(m.group(1))
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start + 1 :]:
        m = re.match(r"^(#{1,3})\s", line)
        if m and len(m.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body)


def cited_sections(text: str, doc: str) -> set[str]:
    """Secciones citadas como `doc` §a.b, §c.d ... dentro de la misma frase."""
    out: set[str] = set()
    pattern = re.compile(re.escape(doc) + r"`?\s*((?:§\d+(?:\.\d+)?(?:\s*(?:,|y|a)\s*)?)+)")
    for m in pattern.finditer(text):
        for lo_a, lo_b, hi_a, hi_b in SEC_RANGE_RE.findall(m.group(1)):
            if lo_a == hi_a:
                for n in range(int(lo_b), int(hi_b) + 1):
                    out.add(f"{lo_a}.{n}")
        out.update(SEC_RE.findall(m.group(1)))
    return out


def check_specs(
    report: Report, arch: str, verif: str, agents: str, defs: str
) -> tuple[dict[str, Path], set[str], set[str]]:
    arch_secs, verif_secs, agents_secs = headings(arch), headings(verif), headings(agents)
    vers = set(VER_RE.findall(verif))
    dom_ids = {f"{f}-{n}" for f, n in DOM_RE.findall(defs)}

    all_defined: dict[str, Path] = {}
    all_decisions: dict[str, Path] = {}
    assigned: set[str] = set()

    for spec_path in SPECS:
        spec = read(spec_path)
        name = spec_path.name
        defined = defined_reqs(spec)

        for rid, where in defined.items():
            if rid in all_defined:
                report.error(
                    f"{name}: {rid} ya esta definido en {all_defined[rid].name}. Los IDs no se reciclan"
                )
            all_defined[rid] = spec_path
            # Las RI de la tabla de rutas no llevan columna de metodo: el suyo lo da la matriz de §7.1
            if where.startswith("|") and not rid.startswith("RI-") and not VER_RE.search(where):
                report.error(f"{name}: {rid} no cita ningun VER-NN en su fila")

        for d in defined_decisions(spec):
            if d in all_decisions:
                report.error(f"{name}: {d} ya esta definida en {all_decisions[d].name}")
            all_decisions[d] = spec_path

        for v in set(VER_RE.findall(spec)) - vers:
            report.error(f"{name}: cita VER-{v}, que no existe en verification.md")

        for sec in cited_sections(spec, "architecture.md") - arch_secs:
            report.error(f"{name}: cita architecture.md §{sec}, que no existe")
        for sec in cited_sections(spec, "verification.md") - verif_secs:
            report.error(f"{name}: cita verification.md §{sec}, que no existe")
        for sec in cited_sections(spec, "AGENTS.md") - agents_secs:
            report.error(f"{name}: cita AGENTS.md §{sec}, que no existe")

        for f, n in set(DOM_RE.findall(spec)):
            if f"{f}-{n}" not in dom_ids:
                report.error(f"{name}: cita {f}-{n}, que no esta en definitions.md")

        # Matriz requisito x metodo: todo requisito definido aparece en 7.1 o en el riesgo aceptado 7.4
        matrix = section(spec, "7.1")
        risk = section(spec, "7.4")
        covered = expand_reqs(matrix) | expand_reqs(risk)
        for rid in defined:
            if rid not in covered:
                report.error(
                    f"{name}: {rid} no aparece en la matriz requisito x metodo (§7.1) ni en el riesgo aceptado (§7.4)"
                )
        for rid in expand_reqs(matrix):
            if rid not in defined and rid not in all_defined:
                report.error(
                    f"{name}: la matriz §7.1 cita {rid}, que no esta definido en ningun SRS"
                )

        # Tramos del plan de ejecucion del SRS
        plan_sec = section(spec, "11")
        assigned |= expand_reqs(plan_sec)

    return all_defined, assigned, set(all_decisions)


def check_plan(
    report: Report,
    arch: str,
    verif: str,
    agents: str,
    defined: dict[str, Path],
    assigned: set[str],
    decisions: set[str],
    plan_path: Path = PLAN,
) -> None:
    plan = read(plan_path)
    label = plan_path.relative_to(ROOT).as_posix()
    arch_secs = headings(arch)

    for rid in expand_reqs(plan):
        if rid not in defined:
            report.error(f"{label}: cita {rid}, que ningun SRS define")
    for d in set(DEC_RE.findall(plan)):
        if f"D-{d}" not in decisions:
            report.error(f"{label}: cita D-{d}, que ningun SRS define")
    for v in set(VER_RE.findall(plan)) - set(VER_RE.findall(verif)):
        report.error(f"{label}: cita VER-{v}, que no existe")
    for sec in cited_sections(plan, "architecture.md") - arch_secs:
        report.error(f"{label}: cita architecture.md §{sec}, que no existe")
    for sec in cited_sections(plan, "verification.md") - headings(verif):
        report.error(f"{label}: cita verification.md §{sec}, que no existe")
    for sec in cited_sections(plan, "AGENTS.md") - headings(agents):
        report.error(f"{label}: cita AGENTS.md §{sec}, que no existe")

    # Todo requisito esta asignado a un tramo: en el §11 de su SRS o en una fila `| Requisitos |` del plan
    plan_assigned = set()
    for line in plan.splitlines():
        if line.startswith("| Requisitos |"):
            plan_assigned |= expand_reqs(line)
    for rid in sorted(defined):
        if plan_path != PLAN:
            break  # el del frontend lo comprueba check_frontend_plan, tramo a tramo
        if rid not in assigned and rid not in plan_assigned:
            report.error(
                f"{rid} ({defined[rid].name}) no esta asignado a ningun tramo, ni en el §11 de su SRS ni en {label}"
            )

    # Matriz de cobertura del plan frente a architecture.md: toda seccion tiene fila
    matrix = section(plan, "7.")
    rows_secs: set[str] = set()
    for line in matrix.splitlines():
        if not line.startswith("| §"):
            continue
        cell = line.split("|")[1]
        for lo_a, lo_b, hi_a, hi_b in SEC_RANGE_RE.findall(cell):
            if lo_a == hi_a:
                for n in range(int(lo_b), int(hi_b) + 1):
                    rows_secs.add(f"{lo_a}.{n}")
        rows_secs.update(SEC_RE.findall(cell))
    for sec in sorted(arch_secs, key=lambda s: [int(x) for x in s.split(".")]):
        top = sec.split(".")[0]
        # Una seccion de primer nivel cuenta como cubierta si lo esta ella o alguna de sus subsecciones
        covered = (
            sec in rows_secs or top in rows_secs or any(r.split(".")[0] == sec for r in rows_secs)
        )
        if not covered:
            report.error(
                f"{label} §7: architecture.md §{sec} no tiene fila en la matriz de cobertura"
            )
    for sec in rows_secs - arch_secs:
        report.error(f"{label} §7: la matriz cita architecture.md §{sec}, que no existe")

    if plan_path != PLAN:
        return

    # Numeros de tramo: unicos entre los §11 de los SRS y los encabezados del plan
    seen: dict[str, str] = {}
    for spec_path in SPECS:
        for line in section(read(spec_path), "11").splitlines():
            m = re.match(r"^\|\s*\*\*T(\d+)\*\*", line)
            if m:
                t = f"T{m.group(1)}"
                if t in seen and seen[t] != spec_path.name:
                    report.error(f"{spec_path.name}: {t} ya esta definido en {seen[t]}")
                seen[t] = spec_path.name
    plan_tramos = re.findall(r"^### (T\d+)", plan, flags=re.M)
    dupes = {t for t in plan_tramos if plan_tramos.count(t) > 1}
    for t in sorted(dupes):
        report.error(f"{label}: el tramo {t} esta definido dos veces")
    v1_tramos = {t for t, s in seen.items() if s == "srs-backend-v1.md"}
    for t in v1_tramos & set(plan_tramos):
        report.error(f"{label}: redefine {t}, que el SRS v1 ya entrego")
    v2_tramos = {t for t, s in seen.items() if s == "srs-backend-v2.md"}
    for t in sorted(v2_tramos - set(plan_tramos)):
        report.error(f"{label}: el SRS v2 define {t} y el plan no lo tiene")


def tramo_assignments(text: str) -> dict[str, set[str]]:
    """Tramo -> requisitos, desde las filas `| **Tn** |` de un §11 o los `### Tn` de un plan."""
    out: dict[str, set[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*\*\*(T\d+)\*\*\s*\|", line)
        if m:
            # | # | Tramo | Que entrega | Requisitos | Puerta |: solo la columna de requisitos
            cells = line.split("|")
            out[m.group(1)] = expand_reqs(cells[4] if len(cells) > 4 else line)
    current = None
    for line in text.splitlines():
        m = re.match(r"^### (T\d+)\b", line)
        if m:
            current = m.group(1)
            out.setdefault(current, set())
        elif re.match(r"^#{1,3}\s", line):
            current = None
        elif current and line.startswith("| Requisitos |"):
            out[current] |= expand_reqs(line)
    return out


def check_frontend_plan(report: Report) -> None:
    """El plan del frontend asigna cada requisito al tramo que le da su SRS, una sola vez."""
    if not FRONTEND_PLAN.exists():
        return
    plan = read(FRONTEND_PLAN)
    spec_tramos = {
        t: ids for t, ids in tramo_assignments(section(read(FRONTEND_SPEC), "11")).items() if ids
    }
    body = plan.split("\n## 7.", 1)[0]
    plan_tramos = {t: ids for t, ids in tramo_assignments(body).items() if t.startswith("T")}
    for t in sorted(set(spec_tramos) - set(plan_tramos)):
        report.error(f"frontend/PLAN.md: el SRS define {t} con requisitos y el plan no lo tiene")
    owner: dict[str, str] = {}
    for t, ids in plan_tramos.items():
        for rid in ids:
            if rid in owner:
                report.error(f"frontend/PLAN.md: {rid} esta en {owner[rid]} y en {t}")
            owner[rid] = t
    for t, ids in spec_tramos.items():
        for rid in sorted(ids):
            if owner.get(rid) != t:
                report.error(
                    f"frontend/PLAN.md: {rid} es de {t} en el SRS y el plan lo pone en {owner.get(rid)}"
                )
    # §7.2: cada fila de requisito cita el tramo que el plan le da
    for line in section(plan, "7.2").splitlines():
        m = re.match(r"^\|\s*((?:RF|RD|RI|RNF)-\d{2,3})\s*\|", line)
        if not m:
            continue
        cited = set(TRAMO_RE.findall(line))
        rid = m.group(1)
        if rid in owner and {owner[rid][1:]} != cited:
            report.error(f"frontend/PLAN.md §7.2: la fila de {rid} no cita su tramo, {owner[rid]}")


def _tree(arch: str, heading: str) -> set[str]:
    """Carpetas del primer bloque de codigo tras `#### heading` en architecture.md §2.3."""
    tree = section(arch, "2.3")
    after = tree.split(f"#### {heading}", 1)[1] if f"#### {heading}" in tree else ""
    block = after.split("```", 2)[1] if after.count("```") >= 2 else ""
    return set(re.findall(r"^[│├└─\s]*([a-z_-]+)/", block, flags=re.M)) - {"backend", "frontend"}


def check_layout(report: Report, arch: str) -> None:
    """Todo paquete de backend/ esta declarado en el arbol de architecture.md §2.3."""
    declared = _tree(arch, "Backend")
    front = _tree(arch, "Frontend")
    if FRONTEND.exists():
        ignored = {"node_modules", "dist", "coverage"}
        for d in sorted(p.name for p in FRONTEND.iterdir() if p.is_dir()):
            if d.startswith(".") or d in ignored:
                continue
            if d not in front:
                report.error(f"frontend/{d}/ es una carpeta que architecture.md §2.3 no declara")
    for pkg in sorted(p.name for p in BACKEND.iterdir() if (p / "__init__.py").exists()):
        if pkg not in declared:
            report.error(f"backend/{pkg}/ es un paquete que architecture.md §2.3 no declara")
    for pkg in sorted(
        declared
        - {"commons", "manuscript", "entity_graph", "tension_curve", "narrative_debt", "run_health"}
    ):
        if pkg in {"app", "pages", "widgets", "features", "entities", "shared"}:
            continue
        if not (BACKEND / pkg / "__init__.py").exists():
            report.note(
                f"architecture.md §2.3 declara backend/{pkg}/ y todavia no existe: pendiente de su tramo"
            )


#: `kind="check.x"` en una llamada o `KIND = "check.x"` como constante: las dos
#: formas en que el codigo da nombre al defecto de un verificador determinista.
KIND_RE = re.compile(r"""\b(?:kind|KIND)\s*=\s*["'](check\.[a-z_]+)["']""")
CHECK_NAME_RE = re.compile(r"`(check\.[a-z_]+)`")
#: Carpetas de backend/ que no son codigo del sistema: tiradas, copias y cachés.
_NOT_CODE = {"runs-golden", "golden", "__pycache__", "node_modules"}
#: Los puntos de ejecucion de §9.1 que la tabla por brief cubre con una columna fija.
_SCENE_POINTS = ("Puerta de escena", "Escena de encuentro")
_NO_POINT = {"", "—", "-"}


def code_check_kinds(backend: Path = BACKEND) -> dict[str, str]:
    """`kind` `check.*` que el codigo asigna -> primer fichero que lo hace, relativo a `backend`."""
    out: dict[str, str] = {}
    for path in sorted(backend.rglob("*.py")):
        rel = path.relative_to(backend)
        if path.name.startswith("test_") or path.name == "coherence.py":
            continue
        if any(p in _NOT_CODE or p.startswith(".") for p in rel.parts[:-1]):
            continue
        for kind in KIND_RE.findall(read(path)):
            out.setdefault(kind, rel.as_posix())
    return out


def code_check_modules(backend: Path = BACKEND) -> dict[str, str]:
    """Modulos de `verification/checks/` que se declaran validador -> su fichero.

    Un verificador que no marca defectos con `kind` propio, como `check.evidence`,
    que descarta citas, existe como modulo: `checks/<x>.py` cuyo docstring abre
    con `` `check.<x>` ``. Un modulo que agrupa varios, como `deterministic.py`,
    no se declara: sus validadores ya salen por su `kind`.
    """
    out: dict[str, str] = {}
    for path in sorted((backend / "verification" / "checks").glob("*.py")):
        if path.name.startswith("test_"):
            continue
        name = f"check.{path.stem}"
        if read(path).lstrip().startswith(f'"""`{name}`'):
            out[name] = path.relative_to(backend).as_posix()
    return out


def validator_rows(arch: str) -> list[tuple[list[str], str]]:
    """Filas de la tabla de §9.1 que nombran un `check.*`: (nombres, punto de ejecucion)."""
    rows: list[tuple[list[str], str]] = []
    col_name = col_point = None
    for line in section(arch, "9.1").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if "Validador" in cells and "Punto de ejecución" in cells:
            col_name, col_point = cells.index("Validador"), cells.index("Punto de ejecución")
            continue
        if col_name is None or col_point is None or len(cells) <= max(col_name, col_point):
            continue
        names = CHECK_NAME_RE.findall(cells[col_name])
        if names:
            rows.append((names, cells[col_point]))
    return rows


def _tuple_names(text: str, name: str) -> set[str]:
    """Los `check.*` literales de la tupla `name = (...)` de un modulo."""
    m = re.search(rf"^{name}\s*=\s*\((.*?)\)", text, flags=re.M | re.S)
    return set(re.findall(r"""["'](check\.[a-z_]+)["']""", m.group(1))) if m else set()


def check_validators(report: Report, arch: str, backend: Path = BACKEND) -> None:
    """RF-268. La tabla de validadores de `architecture.md` §9.1 frente al codigo.

    Todo `kind` `check.*` del codigo, y todo modulo de `verification/checks/` que
    se declara validador, tiene fila; todo `check.*` de una fila existe como una
    de las dos cosas; toda fila dice donde corre. Y la tabla por brief (`evals/brief_table.py`, RF-269) tiene una
    columna fija por cada verificador que la tabla pone en la puerta de escena o
    en la escena de encuentro, ni una mas ni una menos: sin ella, un verificador
    nuevo solo sale cuando marca y nadie puede leer que paso.
    """
    rows = validator_rows(arch)
    if not rows:
        report.error(
            "architecture.md §9.1: no hay tabla de validadores con columnas "
            "Validador y Punto de ejecución, o ninguna fila nombra un check.*"
        )
        return
    in_table = {n for names, _ in rows for n in names}
    kinds = code_check_kinds(backend)
    modules = code_check_modules(backend)

    for kind, where in sorted(kinds.items()):
        if kind not in in_table:
            report.error(
                f"backend/{where} define el kind {kind} y architecture.md §9.1 no tiene fila para el"
            )
    for name, where in sorted(modules.items()):
        if name not in in_table and name not in kinds:
            report.error(
                f"backend/{where} se declara validador {name} y architecture.md §9.1 "
                "no tiene fila para el"
            )
    for names, point in rows:
        for n in names:
            if n not in kinds and n not in modules:
                report.error(
                    f"architecture.md §9.1: la fila de {n} nombra un validador que el codigo "
                    "no define como kind ni como modulo de verification/checks/"
                )
        if point in _NO_POINT:
            report.error(
                f"architecture.md §9.1: la fila de {', '.join(names)} no tiene punto de ejecucion"
            )

    brief_table = backend / "evals" / "brief_table.py"
    if not brief_table.exists():
        return
    text = read(brief_table)
    columns = _tuple_names(text, "SCENE_CHECKS") | _tuple_names(text, "MATCH_CHECKS")
    at_scene = {n for names, point in rows if point.startswith(_SCENE_POINTS) for n in names}
    for n in sorted(columns - at_scene):
        report.error(
            f"evals/brief_table.py tiene columna fija para {n}, que architecture.md §9.1 no "
            "pone en la puerta de escena ni en la escena de encuentro"
        )
    for n in sorted(at_scene - columns):
        report.error(
            f"evals/brief_table.py no tiene columna fija para {n}, que architecture.md §9.1 "
            "pone en la puerta de escena o en la escena de encuentro"
        )


def main() -> int:
    report = Report()
    arch, verif, agents, defs = (
        read(DOCS / "architecture.md"),
        read(DOCS / "verification.md"),
        read(AGENTS),
        read(DOCS / "definitions.md"),
    )
    defined, assigned, decisions = check_specs(report, arch, verif, agents, defs)
    check_plan(report, arch, verif, agents, defined, assigned, decisions)
    if FRONTEND_PLAN.exists():
        check_plan(report, arch, verif, agents, defined, assigned, decisions, FRONTEND_PLAN)
    check_frontend_plan(report)
    check_layout(report, arch)
    check_validators(report, arch)

    for n in report.notes:
        print(f"  nota: {n}")
    if report.errors:
        for e in report.errors:
            print(f"  FALLA: {e}")
        print(f"\ncoherencia: {len(report.errors)} inconsistencias")
        return 1
    print(f"coherencia: {len(defined)} requisitos, {len(SPECS)} SRS, plan y arquitectura alineados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
