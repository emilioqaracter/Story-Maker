# Claves y entorno para trabajar en Story-Maker desde otra máquina

Qué hay que tener a mano para clonar `v2-oneshot` y seguir donde se quedó. Aquí van **solo nombres**: los valores viven en `.env.local`, que está en `.gitignore` y no viaja con el repo. Hay que copiarlos por un canal aparte, por ejemplo el gestor de contraseñas, nunca por el repo ni por un chat.

Sacado del código el 2026-09-24: `backend/commons/settings.py`, `backend/commons/tracing/langfuse_export.py`, `backend/commons/provider/claude_cli.py`, `backend/orchestration/model/run_tlc.sh`, `frontend/visual/tour.mjs` y `.mcp.json`.

## 1. Claves y variables de entorno

| Variable | Para qué | Si falta |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | Espejo de la traza en Langfuse (RI-60) y `python -m orchestration.prompts_sync` | La tirada sigue y queda `export.disabled` en la traza. Sin espejo ni publicación de prompts |
| `LANGFUSE_SECRET_KEY` | Igual que la anterior. Es la que hay que tratar como secreto | Igual |
| `LANGFUSE_BASE_URL` | Host de Langfuse, por ejemplo la nube de la UE o la de EE. UU. | Igual: las tres van juntas o no se envía nada |
| `LANGFUSE_TRACING_ENVIRONMENT` | Opcional. Etiqueta de entorno de las trazas | Sin etiqueta |
| `STORY_MAKER_RUNS` | Carpeta de las novelas: un SQLite y una traza por tirada. En la máquina de la entrega apunta a `backend/runs-real` | El backend usa `./runs` desde donde arranque |
| `JAVA` | Ruta del `java.exe` de TLC, solo para `run_tlc.sh` | Usa la ruta fija de la máquina de la entrega, que en otra máquina no existe |
| `TLA2TOOLS_JAR` | Ruta de `tla2tools.jar`, solo para `run_tlc.sh` | Igual |
| `PYTHON` | Intérprete que usa la validación visual `frontend/visual/tour.mjs` | `python` en Windows, `python3` en el resto |

Lo que **no** hace falta:

- **`ANTHROPIC_API_KEY`**: no se usa. El motor llama a `claude -p` con la autenticación por suscripción de Claude Code (RI-62, D-85). Basta con iniciar sesión en Claude Code en la máquina nueva. `--bare` se descartó justo porque exigiría la clave.
- **Claves del frontend**: no hay ninguna. No lee `import.meta.env` ni `process.env`.
- **Claves del MCP de navegador**: `.mcp.json` lanza `@playwright/mcp` en local, sin cuenta.

Dos avisos:

- Nadie en el código carga `.env.local`: ni `python-dotenv` ni `--env-file`. Las variables tienen que estar en el entorno del shell que arranca `uvicorn`, `gate.py` o `prompts_sync`. El motor las quita del entorno del `claude -p` a propósito, así que estar en el shell no las filtra a la novela.
- El hook `.claude/hooks/policy.py` bloquea que el agente lea `.env*` o ficheros `.pem`, `.key`, `id_rsa`. Es lo esperado: el fichero lo crea y lo rellena la persona, no el agente.

## 2. Programas que hay que instalar

| Herramienta | Versión que hay en la máquina actual | Para qué |
|---|---|---|
| Python | 3.12.10, `requires-python >= 3.12` | Backend, `gate.py`, hooks de Claude Code |
| Node | v24.19.0 | Frontend, `gate.mjs`, validación visual, `npx langfuse-cli` |
| Claude Code CLI | 2.1.263, con sesión iniciada | Es el proveedor de modelo del motor. Sin él no arranca ninguna tirada |
| Lean 4 vía `elan` | `leanprover/lean4:v4.34.0`, lo fija `backend/verification/formal/lean/lean-toolchain` | `lake build` de la cronología. Fallo cerrado: sin `lake` en el PATH la tirada no arranca y `gate.py` falla |
| Java 11 o superior | JDK 21 de Adoptium en la actual | TLC del modelo TLA+, solo al cambiar el modelo |
| `tla2tools.jar` | La que hay en `C:/tools/tla/` en la actual | Igual |
| Microsoft Edge | La del sistema | Navegador del MCP de Playwright, `--browser msedge` |
| Git | Cualquiera | El motor lo busca con `shutil.which("git")` |

## 3. Pasos en la máquina nueva

```powershell
git clone <remoto> Story-Maker
cd Story-Maker
git checkout v2-oneshot

# Backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
# El modelo de embeddings intfloat/multilingual-e5-large se descarga solo la primera vez

# Lean: instala elan y deja que lake resuelva el toolchain que fija lean-toolchain
cd verification\formal\lean
lake build
cd ..\..\..

# Frontend
cd ..\frontend
npm ci
npx playwright install msedge
```

Después, crear `.env.local` en la raíz con las variables de la tabla de §1 y cargarlas en el shell antes de arrancar nada. Comprobación sin mostrar valores:

```powershell
cd backend
python -c "from commons.tracing.langfuse_export import missing_keys; print(missing_keys() or 'Langfuse completo')"
claude --version
lake --version
```

Puertas, en este orden, antes de tocar código:

```powershell
cd backend;  python gate.py     # unos 6 minutos, con Lean
cd frontend; node gate.mjs
```

## 4. Lo que no viaja con el repo y conviene copiar a mano

| Qué | Dónde está | Por qué importa |
|---|---|---|
| `.env.local` | Raíz | Las claves de §1 |
| `backend/runs-real/` | Ignorado por `backend/runs-*/` | Las novelas reales, sus trazas y `enviar-entrega.py`. Si se quiere retomar *El relevo de la bahía* hay que copiar su `.sqlite` y su `.trace.jsonl` |
| `backend/golden/` | Se versiona, pero `golden/v1-seed/` no existe aún | Lo produce la tirada de T16, pendiente |
| `.claude/audit/` | Ignorado | Audit log del hook; en la máquina nueva empieza vacío, y eso está bien |
| `.claude/auditoria-entrega/` | Ignorado | El informe de la auditoría de la entrega. Copiarlo si se quiere seguir con ENT-NN |
| `.claude/*.local.md`, `.claude/spec-loop/` | Ignorados | Ajustes locales del plugin spec-loop |

Pendiente de trabajo al llegar: lo que dice `.claude/handoff/2026-09-24.md`, empezando por pasar las dos puertas.
