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
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from commons.provider.port import Completion, ToolServer, Usage

#: Recortes que bajan el andamiaje de 44.100 a 38.584 fichas. Medido, no
#: estimado. Cada uno quita algo que este sistema no usa.
_TRIM = (
    "--allowedTools", "",                    # sin herramientas del CLI
    "--disable-slash-commands",              # sin skills
    "--strict-mcp-config",                   # sin servidores externos
    "--mcp-config", '{"mcpServers":{}}',
    "--exclude-dynamic-system-prompt-sections",
    "--no-session-persistence",              # cada llamada es independiente
)

#: Suelo de andamiaje medido. Se descuenta del presupuesto disponible para que
#: la admision cuente lo que de verdad va a ocupar la llamada.
HARNESS_TOKENS = 38_600


class ClaudeCliError(RuntimeError):
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
    ) -> Completion:
        """Una ida y vuelta, sin herramientas.

        El prefijo cacheable va como instruccion del sistema y el paquete por la
        entrada estandar. Esa division no es estetica: el sistema es lo estable
        entre llamadas del mismo agente, que es justo lo que el cache necesita
        delante para no invalidarse.
        """
        system = cacheable_prefix
        if output_schema:
            system += (
                "\n\nDevuelves EXCLUSIVAMENTE un JSON valido que cumpla este esquema. "
                "Sin texto alrededor, sin explicaciones, sin bloque de codigo.\n"
                + output_schema
            )

        entrada = f"{packet}\n\n---\n\n{instruction}"
        return self._run(system=system, stdin=entrada, max_output_tokens=max_output_tokens)

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
    ) -> Completion:
        """Bucle de herramientas.

        **No implementado sobre esta via todavia.** El CLI tiene su propio bucle
        de herramientas, pero las que expone son las suyas --leer ficheros,
        ejecutar ordenes-- y no las nuestras, y no hay forma de sustituirlas sin
        pasar por el SDK de agentes.

        Se lanza en vez de degradar en silencio a una llamada suelta: un agente
        que declara herramientas y no las recibe produce respuestas peores sin
        que nada lo señale, que es exactamente el modo de fallo que este sistema
        evita en todo lo demas.
        """
        raise NotImplementedError(
            "el camino de tiron necesita el SDK de agentes; sobre el CLI solo "
            "esta la llamada suelta. Los cinco agentes con herramientas corren "
            "de momento con su paquete empujado, que es lo que reciben igual"
        )

    # --------------------------------------------------------------- embeddings

    def embed(self, texts: Sequence[str], *, is_query: bool) -> Sequence[object]:
        raise NotImplementedError(
            "los embeddings son locales: usa `commons.provider.embeddings`"
        )

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

    def _run(self, *, system: str, stdin: str, max_output_tokens: int) -> Completion:
        cmd = [
            self._resolve(), "-p",
            "--model", self.model,
            "--output-format", "json",
            "--max-turns", "1",
            "--system-prompt", system,
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
            raise ClaudeCliError(
                f"el CLI no respondio en {self.timeout_s}s"
            ) from exc

        if proc.returncode != 0:
            raise ClaudeCliError(
                f"el CLI salio con codigo {proc.returncode}: {proc.stderr[:400]}"
            )

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeCliError(
                f"el CLI no devolvio JSON: {proc.stdout[:300]}"
            ) from exc

        if data.get("is_error"):
            raise ClaudeCliError(f"el CLI devolvio error: {data.get('result', '')[:300]}")

        u = data.get("usage", {})
        return Completion(
            text=_strip_fence(str(data.get("result", ""))),
            usage=Usage(
                input_tokens=int(u.get("input_tokens", 0)),
                cache_creation_tokens=int(u.get("cache_creation_input_tokens", 0)),
                cache_read_tokens=int(u.get("cache_read_input_tokens", 0)),
                output_tokens=int(u.get("output_tokens", 0)),
            ),
            stop_reason=str(data.get("stop_reason", "end_turn")),
            tool_calls=(),
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
