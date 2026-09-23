"""Cliente de Claude sobre el CLI de Claude Code.

Usa la **suscripcion** del usuario en vez de una clave de API. Eso tiene una
consecuencia medida que condiciona los presupuestos, y conviene tenerla delante:

**El CLI manda su propio andamiaje en cada llamada.** Instrucciones del sistema
y definiciones de herramientas, ~38.600 fichas incluso con todos los recortes
aplicados. El modo minimo del CLI lo quitaria, pero **exige clave de API**, asi
que por esta via es un suelo.

Cabe de sobra igualmente. La ventana de Haiku son 200.000 y los presupuestos por
agente estan muy por debajo del techo:

    andamiaje  38.600  +  Escritor    19.700  =   58.300
    andamiaje  38.600  +  Continuista 72.500  =  111.100

El techo de 100.000 nunca estuvo pensado para usarse entero, y aqui se nota.

**El cache sobrevive entre invocaciones** --medido: la segunda llamada leyo
37.154 fichas de cache en vez de crearlas-- asi que el andamiaje se paga caro
una vez y barato despues. Por eso el prefijo cacheable va en la instruccion del
sistema, que es lo unico estable entre llamadas del mismo agente.
"""

from __future__ import annotations

import json
import shutil

# La lista de comandos se arma en este modulo y no entra nada del exterior:
# el unico dato variable es la ruta que resuelve `shutil.which`.
import subprocess  # nosec B404
from collections.abc import Sequence
from dataclasses import dataclass

from commons.provider.port import (
    Completion,
    Embedding,
    ProviderError,
    ToolCall,
    ToolServer,
    Usage,
)

#: Recortes que bajan el andamiaje de 44.100 a 38.584 fichas. Medido, no
#: estimado. Cada uno quita algo que este sistema no usa.
_TRIM = (
    "--allowedTools",
    "",  # sin herramientas del CLI
    "--disable-slash-commands",  # sin skills
    "--strict-mcp-config",  # sin servidores externos
    "--mcp-config",
    '{"mcpServers":{}}',
    "--exclude-dynamic-system-prompt-sections",
    "--no-session-persistence",  # cada llamada es independiente
)

#: Suelo de andamiaje medido. Se descuenta del presupuesto disponible para que
#: la admision cuente lo que de verdad va a ocupar la llamada.
HARNESS_TOKENS = 38_600

#: Red de seguridad del bucle de herramientas, no un cupo: el cupo lo lleva el
#: servidor en tokens (RF-97). Esto solo impide que un modelo que ignora dos
#: negativas seguidas siga pidiendo para siempre. Es el mismo papel que el tope
#: de salida de 50.000 en `dispatch`.
MAX_TOOL_TURNS = 12


def _tool_protocol(tools: Sequence[str]) -> str:
    """Como se pide una herramienta. Va en el prefijo: es estable por agente."""
    if not tools:
        return ""
    lista = "\n".join(f"- {t}" for t in tools)
    return (
        "\n\nHERRAMIENTAS\n"
        "Puedes consultar antes de concluir. Para pedir una consulta, devuelve SOLO "
        'este JSON y nada mas: {"tool": "<nombre>", "arguments": {...}}. '
        "Recibiras el resultado y volveras a decidir. Solo existen estas:\n" + lista + "\n"
        "canon.lookup admite arguments: {kind: entity|knowledge|related, entity_ids: [...], "
        "entity_id: ..., full: true|false}. context.budget no lleva arguments.\n"
        "Cada resultado consume tu cupo; cuando no quepa, se te dira y tendras que "
        "concluir con lo que tienes."
    )


def _tool_request(text: str) -> ToolCall | None:
    """Si la salida es una peticion de herramienta, la devuelve; si no, `None`."""
    limpio = _strip_fence(text)
    if not limpio.startswith("{"):
        return None
    try:
        data = json.loads(limpio)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "tool" not in data:
        return None
    return ToolCall(name=str(data["tool"]), arguments=json.dumps(data.get("arguments", {})))


def _sum_usage(a: Usage, b: Usage) -> Usage:
    return Usage(
        input_tokens=a.input_tokens + b.input_tokens,
        cache_creation_tokens=a.cache_creation_tokens + b.cache_creation_tokens,
        cache_read_tokens=a.cache_read_tokens + b.cache_read_tokens,
        output_tokens=a.output_tokens + b.output_tokens,
    )


class ClaudeCliError(ProviderError):
    """El CLI no devolvio una respuesta utilizable.

    Cuenta como llamada fallida y consume un reintento: no se reintenta aqui
    dentro, porque los reintentos son del Orquestador y tienen presupuesto.
    """


@dataclass(frozen=True)
class ClaudeCli:
    """Puerto de proveedor implementado sobre el CLI.

    `model` es un alias del CLI --haiku, sonnet, opus-- y no un identificador
    completo: el CLI resuelve la version, y fijarla aqui obligaria a tocar
    codigo cada vez que salga una nueva.
    """

    model: str = "haiku"
    timeout_s: int = 600
    executable: str = "claude"

    # ------------------------------------------------------------- una vuelta

    def complete_once(
        self,
        *,
        cacheable_prefix: str,
        packet: str,
        instruction: str,
        output_schema: str,
        max_output_tokens: int,
        json_schema: str | None = None,
    ) -> Completion:
        """Una ida y vuelta, sin herramientas.

        El prefijo cacheable va como instruccion del sistema y el paquete por la
        entrada estandar. Esa division no es estetica: el sistema es lo estable
        entre llamadas del mismo agente, que es justo lo que el cache necesita
        delante para no invalidarse.

        El esquema va al **final** de la entrada, no en el sistema. Medido en la
        primera tirada real: con el esquema en el sistema el modelo devolvia
        markdown o claves inventadas, porque el CLI antepone su propio andamiaje
        y lo ultimo que se lee es lo que mas pesa (CTX-16). Y cuando hay esquema
        JSON, el CLI lo hace cumplir con `--json-schema`.
        """
        entrada = f"{packet}\n\n---\n\n{instruction}" + _schema_tail(output_schema)
        return self._run(
            system=cacheable_prefix,
            stdin=entrada,
            max_output_tokens=max_output_tokens,
            json_schema=json_schema,
        )

    # -------------------------------------------------------- con herramientas

    def complete_with_tools(
        self,
        *,
        cacheable_prefix: str,
        packet: str,
        instruction: str,
        output_schema: str,
        max_output_tokens: int,
        tools: Sequence[str],
        server: ToolServer,
        json_schema: str | None = None,
    ) -> Completion:
        """Bucle de herramientas sobre el CLI, por protocolo (D-46).

        El CLI tiene su propio bucle de herramientas, pero las que expone son las
        suyas --leer ficheros, ejecutar ordenes-- y no las nuestras. Asi que el
        bucle se lleva **desde fuera**: en cada turno el modelo devuelve o bien
        una peticion de herramienta en JSON, o bien su respuesta final. La
        peticion se sirve contra el servidor de `orchestration/`, que lleva el
        contador y el cupo, y el resultado se anade al turno siguiente.

        Lo que esto conserva del diseno: la lista de herramientas es cerrada, el
        cupo lo aplica el servidor y no el modelo, cada consulta queda trazada
        con su coste, y el prefijo cacheable sigue siendo lo unico estable.

        Lo que cuesta: cada turno reenvia el paquete. Con el cupo acotado y el
        prefijo cacheado es asumible, y es el precio de no depender de una via
        que exige clave de API.
        """
        system = cacheable_prefix + _tool_protocol(tools)
        cola_esquema = _schema_tail(output_schema, when_done=True)

        exchanges: list[str] = []
        calls: list[ToolCall] = []
        refusals = 0
        usage = Usage(input_tokens=0, output_tokens=0)
        stop = "end_turn"

        for turno in range(MAX_TOOL_TURNS):
            cola = "\n\n".join(exchanges)
            entrada = (
                f"{packet}\n\n---\n\n{instruction}"
                + (f"\n\n---\n\n{cola}" if cola else "")
                + cola_esquema
            )
            if refusals >= 2 or turno == MAX_TOOL_TURNS - 1:
                entrada += "\n\n---\n\nNo quedan consultas: concluye AHORA con tu respuesta final."
            paso = self._run(system=system, stdin=entrada, max_output_tokens=max_output_tokens)
            usage = _sum_usage(usage, paso.usage)
            stop = paso.stop_reason

            peticion = _tool_request(paso.text)
            if peticion is None or refusals >= 2 or turno == MAX_TOOL_TURNS - 1:
                return Completion(
                    text=paso.text,
                    usage=usage,
                    stop_reason=stop,
                    tool_calls=tuple(calls),
                    harness_tokens=HARNESS_TOKENS,
                )

            calls.append(peticion)
            try:
                resultado = server.serve(peticion)
            except Exception as exc:  # la lista cerrada y el cupo hablan por aqui
                exchanges.append(f"RESULTADO DE {peticion.name}: rechazado. {exc}")
                refusals += 1
                continue
            if resultado.refused:
                refusals += 1
            else:
                refusals = 0
            exchanges.append(
                f"RESULTADO DE {peticion.name} [procedencia: {resultado.provenance.value}"
                f"{', NO CABE' if resultado.refused else ''}]:\n{resultado.content}"
            )

        raise ClaudeCliError("el bucle de herramientas no concluyo")  # pragma: no cover

    # --------------------------------------------------------------- embeddings

    def embed(self, texts: Sequence[str], *, is_query: bool) -> Sequence[Embedding]:
        raise NotImplementedError("los embeddings son locales: usa `commons.provider.embeddings`")

    def count_tokens(self, text: str, model_id: str) -> int:
        """Recuento real. Lo da la propia llamada, asi que aqui no hace falta."""
        raise NotImplementedError("el recuento real viene en `usage` de cada respuesta")

    # ------------------------------------------------------------------ interno

    def _resolve(self) -> str:
        """Ruta real del ejecutable.

        En Windows `claude` es un envoltorio de npm --un `.cmd`-- y lanzarlo por
        nombre pelado falla con "no se encuentra el archivo". `shutil.which`
        resuelve la extension que toque en cada sistema, asi que el cliente no
        necesita saber en cual corre.
        """
        ruta = shutil.which(self.executable)
        if ruta is None:
            raise ClaudeCliError(
                f"no se encuentra {self.executable!r} en el PATH. "
                "Instala Claude Code o indica otra ruta en `executable`"
            )
        return ruta

    def _run(
        self, *, system: str, stdin: str, max_output_tokens: int, json_schema: str | None = None
    ) -> Completion:
        # Con esquema, el CLI resuelve la salida estructurada en un turno mas:
        # el modelo produce el JSON como una llamada interna y el CLI la valida.
        cmd = [
            self._resolve(),
            "-p",
            "--model",
            self.model,
            "--output-format",
            "json",
            "--max-turns",
            "2" if json_schema else "1",
            "--system-prompt",
            system,
            *(["--json-schema", json_schema] if json_schema else []),
            *_TRIM,
        ]

        try:
            proc = subprocess.run(  # nosec B603
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCliError(f"el CLI no respondio en {self.timeout_s}s") from exc

        if proc.returncode != 0:
            raise ClaudeCliError(f"el CLI salio con codigo {proc.returncode}: {proc.stderr[:400]}")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeCliError(f"el CLI no devolvio JSON: {proc.stdout[:300]}") from exc

        if data.get("is_error"):
            raise ClaudeCliError(f"el CLI devolvio error: {data.get('result', '')[:300]}")

        u = data.get("usage", {})
        salida = data.get("structured_output")
        texto = (
            json.dumps(salida, ensure_ascii=False)
            if salida is not None
            else str(data.get("result", ""))
        )
        return Completion(
            text=_strip_fence(texto),
            usage=Usage(
                input_tokens=int(u.get("input_tokens", 0)),
                cache_creation_tokens=int(u.get("cache_creation_input_tokens", 0)),
                cache_read_tokens=int(u.get("cache_read_input_tokens", 0)),
                output_tokens=int(u.get("output_tokens", 0)),
            ),
            stop_reason=str(data.get("stop_reason", "end_turn")),
            tool_calls=(),
            # Con esquema, la salida estructurada cuesta un turno mas y el
            # andamiaje se paga dos veces (medido: 39.129 creados + 38.742
            # leidos de cache en una llamada minima). Se declara, para que
            # RNF-19 compare lo comparable.
            harness_tokens=HARNESS_TOKENS * (2 if json_schema else 1),
        )


def _schema_tail(output_schema: str, *, when_done: bool = False) -> str:
    """El formato de salida, como ultimo tramo de la entrada."""
    if not output_schema:
        return ""
    cuando = "Cuando concluyas, devuelves" if when_done else "Devuelves"
    return (
        f"\n\n---\n\nFORMATO DE SALIDA, OBLIGATORIO: {cuando} EXCLUSIVAMENTE un JSON valido "
        "con EXACTAMENTE las claves que describe este esquema, en ingles y tal cual se "
        "escriben aqui. Sin texto antes ni despues, sin explicaciones, sin bloque de "
        "codigo, sin claves propias.\n" + output_schema
    )


def _strip_fence(text: str) -> str:
    """Quita el bloque de codigo si el modelo lo puso igual.

    Se pide JSON sin bloque y aun asi lo envuelve a veces. Quitarlo aqui es
    preferible a que la validacion lo rechace: el contenido es correcto y
    fallar por el envoltorio gastaria un reintento por nada.
    """
    limpio = text.strip()
    if not limpio.startswith("```"):
        return limpio
    lineas = limpio.splitlines()
    if lineas and lineas[0].startswith("```"):
        lineas = lineas[1:]
    if lineas and lineas[-1].strip() == "```":
        lineas = lineas[:-1]
    return "\n".join(lineas).strip()
