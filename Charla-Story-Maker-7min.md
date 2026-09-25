# Story-Maker · Charla de venta de 7 minutos

Contenido: investigación de mercado, plan de la charla con tiempos y, al final, el prompt listo para pegar en Claude Design.
Base del producto: rama `v2-oneshot` del repositorio Story-Maker (estado a 24-09-2026).

---

## 1. Qué es el producto, en una frase

**Una novela escrita a medida para regalar**: quien la encarga responde a una entrevista sobre el destinatario (nombre, edad, rasgos, recuerdos, tono, género, dedicatoria, palabras y temas prohibidos) y el sistema escribe, verifica y cierra una novela completa **sin intervención humana**, con el destinatario como protagonista y sus recuerdos reales anclados en el texto.

Formatos de obra que ya existen en el código (`backend/commons/types/length.py`):

| Perfil | Capítulos | Palabras | Uso comercial sugerido |
|---|---|---|---|
| `corta` | 5 × 1 escena | 5.000–7.500 | Regalo exprés / digital |
| `breve` | 10 × 1 escena | 10.000–15.000 | **Producto estrella** (novela corta regalo) |
| `novela` | Según extensión | Largo (hasta ~200.000) | Premium / edición especial |

Lo que ve el cliente (frontend React): entrevista guiada, portada con dedicatoria, índice, lectura por capítulos, **libro en 3D al cerrar la obra**, ficha de personajes y lugares, y **peticiones de cambio desde la lectura** («el perro se llama Nala») que el sistema aplica solo y entrega como versión nueva, sin perder la anterior.

---

## 2. Investigación de mercado (datos con fuente)

### 2.1 El mercado del libro en España está en máximos

| Dato | Cifra | Fuente |
|---|---|---|
| Facturación del sector editorial 2025 (mercado interior) | **3.138,5 M€**, +3,3 %; 12.º año seguido de crecimiento; +43 % desde 2014 | Federación de Gremios de Editores (FGEE), avance jun-2026 |
| Ficción adulta | **831 M€, +17,2 %** | FGEE |
| Infantil y juvenil | 650 M€, +17,8 % | FGEE |
| Ejemplares vendidos / precio medio | 196 M ejemplares; **15,00 €** de media | FGEE |
| Mercado de consumo en librería (panel GfK) | ~1.250 M€, +4 %; +35 % desde 2019 | GfK vía AEA |
| Estacionalidad | Navidad 8,7 % + Reyes 4,6 % + Sant Jordi 3,9 % de las ventas anuales | GfK vía AEA |
| Población que lee en su tiempo libre | **66,2 %** (máximo histórico) | Barómetro de Hábitos de Lectura 2025 |
| Población que compró algún libro (no de texto) | **54,1 %**; internet ya es el 24 % de las compras | Barómetro 2025 |

**Lectura para la charla:** la gente lee más que nunca, compra libros como regalo en picos muy marcados (Navidad, Reyes, Sant Jordi, San Valentín, Día de la Madre/Padre) y la ficción es el segmento que más crece.

### 2.2 El nicho del libro personalizado crece el doble que el libro

| Dato | Cifra | Fuente |
|---|---|---|
| Mercado global del libro 2025 | 156,6 bn US$, CAGR 4,1 % hasta 2033; Europa ≈ 25,8 % | Grand View Research |
| Libro infantil personalizado (global) | 0,73 bn US$ (2026) → 1,5 bn US$ (2035), **CAGR 10,4 %** | Business Research Insights |
| Regalos personalizados (global) | +10,76 bn US$ entre 2025 y 2029, CAGR 6,7 % | Technavio |
| **Caso de validación: Wonderbly** | +11 M de libros personalizados vendidos, 140+ países; **comprada por Penguin Random House en junio de 2025** | Penguin Random House |

**Lectura para la charla:** el mayor grupo editorial del mundo ha pagado por entrar en el libro personalizado. El modelo está validado; lo que falta es el salto de «cuento con tu nombre» a **novela de verdad escrita para ti**.

### 2.3 Competencia y hueco

| Competidor | Qué ofrece | Precio | Limitación |
|---|---|---|---|
| Wonderbly, Hooray Heroes, Mumablue | Cuentos ilustrados con plantilla; cambia nombre y aspecto | 30–45 € | Infantil, historia fija |
| Cuentoslandia (ES) | Cuento de pareja con IA, 24 páginas, 4 capítulos | PDF gratis / 35 € impreso | Muy corto, sin control de coherencia |
| GiftBookStory (UK) | Libro de ~200 páginas generado con IA en 30–45 min | 9,99 £ digital / desde 24,99 £ impreso | Generación en bruto, sin verificación declarada, en inglés |
| Book by Anyone (US) | Novelas de humor «con tu nombre» | — | Plantilla/sátira |

**Nuestro hueco:** novela en español, para adultos o jóvenes, con **garantías verificables de calidad y coherencia** (el personaje no cambia de nombre, las fechas cuadran, los recuerdos del destinatario aparecen de verdad, las palabras prohibidas no salen) y **cambios posteriores sin coste de reescritura manual**.

### 2.4 Tamaño de oportunidad (escenario ilustrativo, no previsión)

- Compradores de libros en España: 54,1 % de la población de 14+ años ≈ **22 millones de personas** (estimación propia sobre ~41 M de habitantes de 14+).
- Si el **0,05 %** compra una novela regalo al año → **~11.000 novelas**.
- A 59 € de precio medio → **~650.000 € de facturación anual** solo en España, sin contar LatAm (donde Qaracter ya opera: México, Brasil, Argentina) ni B2B (editoriales, regalos de empresa, bodas, jubilaciones).

---

## 3. Datos económicos del producto

### 3.1 Coste y tiempo medidos en el propio sistema (rama `v2-oneshot`)

| Medida real (24-09-2026) | Valor |
|---|---|
| Obra `prueba`, 3 capítulos (~1.500 palabras) | **~11 min, 1,75 US$, 54 llamadas de modelo** — cerró completa |
| Obra `corta`, 5 capítulos | ~2,5 min por capítulo |
| Modelo | Claude Haiku 4.5 (11 agentes de modelo), con techo de 100.000 tokens por llamada |

El frontend ya muestra al cliente «Tiempo de redacción» y «Coste» de cada tirada (D-138).

### 3.2 Unit economics por novela `breve` (hipótesis a validar)

| Concepto | Estimación | Cómo se calcula |
|---|---|---|
| Generación IA | **≈ 10–15 US$ (≈ 9–13 €)** | Extrapolación lineal desde `prueba` (1,17 US$ / 1.000 palabras) × 12.500 palabras; cota alta, hay coste fijo que no escala |
| Tiempo de generación | ≈ 25–40 min | 10 capítulos × 2,5–4 min |
| Impresión bajo demanda | 2–12 € | Tapa blanda ~60–80 págs.: KDP = 0,75 € + 0,012 €/pág ≈ 1,5–1,7 €; tapa dura premium hasta ~12 € |
| Envío | ~5 € | Península |
| Pasarela de pago | ~3 % | |

| Precio de venta (IVA libro 4 %, *verificar con asesor fiscal*) | Ingreso neto | Coste total | Margen bruto |
|---|---|---|---|
| **Digital 29 €** | 27,9 € | ~14 € | **~14 € (≈ 50 %)** |
| **Impresa 59 €** | 56,7 € | ~32 € | **~25 € (≈ 44 %)** |
| **Premium tapa dura 89 €** | 85,6 € | ~34 € | **~51 € (≈ 60 %)** |

Palancas de mejora del margen: caché de prompts (ya diseñado: prefijos ≥ 4.096 tokens en Haiku), modelos por agente, y bajada continua del precio por token.

**Aviso honesto para la charla:** hoy el motor corre con el CLI de Claude y la suscripción del autor; para producción hay que pasar a la API con contrato empresarial. El coste de la tabla ya es el equivalente de API que reporta el sistema.

---

## 4. Arquitectura (lo que hay que contar en 60 segundos)

- **Idea central:** una novela larga no es un texto largo, es **un estado del mundo que evoluciona**. El canon (quién es quién, qué pasó y cuándo) es la fuente de verdad; la prosa es una proyección.
- **13 agentes especializados**: Orquestador (código), Arquitecto narrativo, Planificador, Documentalista (código), Escritor, Especialista deportivo, Continuista, Jurado (3 instancias), Reparador, Estilista, Archivero, Árbitro y Supervisor.
- **Memoria en 5 almacenes** (SQLite, un fichero por novela): canon estructurado, registro de eventos append-only, grafo de entidades, índice de prosa (búsqueda híbrida léxica + semántica con embeddings locales) y resúmenes jerárquicos.
- **Ciclo por capítulo:** planificar → ensamblar contexto → escribir → verificar → reparar → juzgar → congelar. Si algo se bloquea, **replanifica en vez de parar**.
- **Stack:** Python + FastAPI (backend), React + TypeScript (frontend), contrato OpenAPI único entre ambos.

### Calidad verificable (el argumento diferencial)

| Capa | Qué garantiza |
|---|---|
| Verificadores deterministas (código, sin IA) | Fechas, nombres, longitudes, repeticiones, **palabras prohibidas** |
| Jurado de 3 jueces, 9 dimensiones | Voz, ritmo, tono, arco, continuidad… y **personalización**: cada recuerdo del destinatario debe aparecer con cita literal |
| Verificación formal **Lean 4** | La cronología del canon es consistente (edades, fechas) antes de congelar un capítulo |
| Model checking **TLA+** | El flujo completo no se bloquea ni congela dos veces |
| Examen de comprensión sin contexto | Un lector «ciego» entiende la historia |

---

## 5. Seguridad y privacidad del proyecto

| Riesgo | Contramedida implementada |
|---|---|
| Datos personales del destinatario (RGPD) | **Un fichero SQLite por novela, en local**: borrar la novela es borrar el fichero. Embeddings calculados en local. El motor lanza cada llamada sin plugins ni configuración de usuario para que el brief no salga por vías no decididas |
| Prompt injection en el texto libre del cliente | Texto delimitado como «material no confiable»; salida validada por esquema; ningún hecho entra sin que la persona lo acepte. **Probado con campaña adversaria real: la inyección no entró** (`evals/results/adversarial-02.md`) |
| Contenido inapropiado | Palabras prohibidas en 3 niveles (global, cliente, novela) y temas vetados en la entrevista; bloqueo determinista |
| «Envenenamiento de canon» (un agente reescribe hechos para taparse) | Solo el Archivero escribe canon, todo cambio pasa por arbitraje, los retcons conservan la versión anterior |
| Ejecución | Backend en contenedor sin más red que la del proveedor de modelo y la observabilidad (Langfuse); canon en solo lectura |
| Secretos | Claves solo en variables de entorno; un hook deniega leer `.env`; audit log con cadena de hashes |
| Regulación IA | AI Act art. 50 aplicable desde el 2-08-2026: para obras de ficción basta un aviso discreto de que el texto está generado con IA → incluir «Escrita con IA» en créditos |
| Garantía corporativa | Qaracter certificada **ISO 27001** e **ISO 9001** |

---

## 6. Por qué Qaracter

- Consultora de tecnología y negocio con presencia en **España, EE. UU., México, Brasil, Argentina, Reino Unido y Polonia** → mercado hispanohablante listo para escalar.
- Área **Exponential Technologies** con experiencia construyendo soluciones de IA en entornos regulados (banca y seguros): copilotos, KYC/AML, clasificación documental.
- **ISO 27001 / ISO 9001**, reconocida por Forbes entre las 100 mejores empresas para trabajar en España.
- Traemos la disciplina de un entorno regulado a un producto de consumo: trazabilidad, verificación formal, seguridad por diseño.

---

## 7. Plan de la charla (7 minutos · 10 diapositivas)

| # | Tiempo | Diapositiva | Qué decir (idea clave) |
|---|---|---|---|
| 1 | 0:00–0:30 | **Gancho** | «¿Cuál es el mejor regalo que te han hecho? Imagina abrir un libro y descubrir que el protagonista eres tú, con tus recuerdos y tu humor. No un cuento con tu nombre: una novela.» |
| 2 | 0:30–1:20 | **El mercado** | 3.138 M€ y 12 años creciendo; la ficción +17 %; 2 de cada 3 españoles leen. Los regalos concentran picos: Navidad, Reyes, Sant Jordi. |
| 3 | 1:20–2:00 | **La señal** | El libro personalizado crece al 10 % anual, el doble que el libro. Penguin Random House compró Wonderbly (11 M de libros vendidos) en 2025. |
| 4 | 2:00–2:40 | **El hueco** | Hoy solo hay cuentos con plantilla o textos de IA sin control. Nadie ofrece una novela en español con calidad garantizada. |
| 5 | 2:40–3:40 | **El producto** (demo o capturas) | Entrevista de 10 min → novela en menos de una hora → libro en 3D, dedicatoria, ficha de personajes → «el perro se llama Nala» y se reescribe sola. |
| 6 | 3:40–4:30 | **Cómo funciona** | 13 agentes, el canon como fuente de verdad, verificación con código, jurado y hasta matemática formal (Lean 4, TLA+). «Por eso los nombres no cambian y los recuerdos aparecen de verdad.» |
| 7 | 4:30–5:10 | **Seguridad** | Datos del destinatario aislados por novela, defensa probada contra inyección, palabras y temas vetados, ISO 27001, AI Act cubierto. |
| 8 | 5:10–6:00 | **Números** | 1,75 US$ y 11 min una obra de prueba real. Novela regalo: coste ≈ 20–30 €, precio 59 €, margen ≈ 45 %. Escenario: 11.000 novelas/año ≈ 650 k€ solo en España. |
| 9 | 6:00–6:40 | **Por qué nosotros** | Qaracter: IA en entornos regulados, 7 países, LatAm incluida. Piloto funcional ya construido. |
| 10 | 6:40–7:00 | **Cierre y petición** | «Te propongo un piloto: encargamos juntos la primera novela para alguien a quien quieras sorprender esta Navidad.» + la petición concreta (inversión / acuerdo / piloto). |

**Consejos de ritmo:** ~140 palabras por minuto → unas 980 palabras de guion en total. Ensaya con cronómetro; si vas tarde, recorta la diapositiva 6 (arquitectura) a una sola frase. Lleva impresa o en tablet una novela real generada: tocarla vende más que cualquier cifra.

**Preguntas probables y respuesta corta:**

- *¿La calidad es de escritor?* — Es una novela corta de regalo, no literatura de autor; lo que garantizamos es coherencia y personalización verificadas. El jurado puntúa 9 dimensiones.
- *¿Qué pasa con los datos?* — Un fichero por novela, borrable, embeddings locales, ISO 27001.
- *¿En qué punto está?* — Sistema completo construido y probado; cierre de las tiradas de evaluación en curso y paso a API empresarial como siguiente hito.

---

## 8. PROMPT PARA CLAUDE DESIGN (copiar y pegar)

```
Actúa como diseñador/a de presentaciones de negocio. Crea una presentación de 10 diapositivas en español (formato 16:9) para una charla de venta de 7 minutos. La presenta Qaracter, una consultora tecnológica, a una persona a la que queremos vender o asociar en un producto nuevo: "Story-Maker", novelas escritas a medida con IA para regalar.

OBJETIVO
Que la persona salga con ganas de comprar o invertir: emoción al principio, datos sólidos en medio, confianza (seguridad y equipo) y una petición clara al final. Tono cálido, seguro, profesional; nada de jerga innecesaria.

IDENTIDAD VISUAL
- Paleta corporativa: fondo #FFFFFF, gris tarjeta #F5F5F5, azul titulares #1E2D3D, gris cuerpo #4A5763, naranja acento #F4631E. Máximo dos elementos naranjas por diapositiva. El verde #2F9E6B solo para indicar "éxito/validado".
- Tipografías: Literata (serif) para citas, fragmentos de novela y frases emocionales; JetBrains Mono para cifras, costes y datos medidos; una sans limpia (p. ej. Inter) para titulares y texto.
- Estética: editorial y literaria (papel, libro, dedicatoria) combinada con precisión tecnológica. Mucho aire, una idea por diapositiva, cifras grandes.
- Deja un hueco arriba a la izquierda para el logo de Qaracter (versión negativa, blanca: solo sobre fondo oscuro #1E2D3D).
- Incluye notas del orador en cada diapositiva con el texto a decir y su tiempo.

DIAPOSITIVAS

1. PORTADA / GANCHO (0:00–0:30)
Título: "El regalo que nadie más puede hacer"
Subtítulo: "Una novela escrita para una sola persona."
Visual: un libro abierto con una dedicatoria manuscrita. Fondo azul #1E2D3D.
Notas: "¿Cuál es el mejor regalo que te han hecho? Imagina abrir un libro y descubrir que el protagonista eres tú, con tus recuerdos. No un cuento con tu nombre: una novela."

2. EL MERCADO (0:30–1:20)
Título: "La gente lee más que nunca"
Cifras grandes: "3.138 M€ facturación del libro en España 2025 (+3,3 %, 12 años creciendo)" · "Ficción adulta +17,2 %" · "66,2 % de los españoles lee en su tiempo libre".
Mini gráfico de barras de estacionalidad del regalo: Navidad 8,7 %, Reyes 4,6 %, Sant Jordi 3,9 % de las ventas anuales.
Fuentes al pie (pequeño): FGEE Comercio Interior 2025; GfK; Barómetro de Hábitos de Lectura 2025.

3. LA SEÑAL (1:20–2:00)
Título: "Lo personalizado crece el doble"
Comparativa visual: libro en general CAGR 4,1 % vs libro personalizado CAGR 10,4 % (0,73 → 1,5 bn US$ 2026-2035).
Destacado: "Penguin Random House compró Wonderbly en 2025: más de 11 millones de libros personalizados vendidos en 140 países."
Fuentes: Grand View Research; Business Research Insights; Penguin Random House.

4. EL HUECO (2:00–2:40)
Título: "Hoy solo hay cuentos con plantilla"
Mapa de posicionamiento 2x2: eje X "plantilla → escrita a medida", eje Y "sin control de calidad → calidad verificada". Competidores (Wonderbly, Hooray Heroes, cuentos de pareja con IA, generadores de libros con IA) en los cuadrantes de plantilla o sin control; Story-Maker solo en el cuadrante superior derecho, en naranja.
Frase: "Nadie ofrece una novela en español con calidad garantizada."

5. EL PRODUCTO (2:40–3:40)
Título: "De una conversación a una novela"
Flujo horizontal de 4 pasos con iconos: 1) Entrevista de 10 minutos sobre el destinatario (rasgos, recuerdos, tono, dedicatoria, temas prohibidos) → 2) El sistema escribe y verifica la novela sola, en menos de una hora → 3) Lectura con portada, dedicatoria, índice, ficha de personajes y libro en 3D → 4) "El perro se llama Nala": pides un cambio y se reescribe sola en una nueva versión.
Espacio para una captura de la app (dejar marco de placeholder).
Formatos: Corta (5 capítulos) · Breve (10 capítulos, producto estrella) · Novela (premium).

6. CÓMO FUNCIONA (3:40–4:30)
Título: "13 agentes y un canon que no olvida"
Diagrama: en el centro "Canon: la fuente de verdad" (5 almacenes de memoria). Alrededor, agentes agrupados: Planificación (Arquitecto, Planificador), Escritura (Escritor, Estilista), Verificación (Continuista, Jurado x3, Reparador), Memoria (Archivero, Árbitro), Supervisión (Supervisor), dirigidos por un Orquestador.
Franja inferior "Calidad verificable": Verificación con código · Jurado de 9 dimensiones (incluida personalización) · Matemática formal Lean 4 y TLA+ · Examen de comprensión.
Frase: "Por eso los nombres no cambian, las fechas cuadran y los recuerdos aparecen de verdad."

7. SEGURIDAD (4:30–5:10)
Título: "Seguro por diseño"
Cuadrícula de 6 tarjetas con icono: Datos aislados (un fichero por novela, borrable; embeddings locales) · Inyección de instrucciones probada y bloqueada · Palabras y temas vetados en 3 niveles · Contenedor sin red salvo el proveedor de IA · Secretos fuera del código y auditoría con cadena de hashes · Cumplimiento: RGPD, AI Act art. 50, Qaracter ISO 27001 / ISO 9001.

8. LOS NÚMEROS (5:10–6:00)
Título: "Un negocio con margen"
Izquierda, dato real medido: "Obra de prueba: 11 min · 1,75 US$ · 54 llamadas de IA" (en JetBrains Mono, con indicador verde "medido").
Centro, tabla de precios: Digital 29 € (margen ≈ 50 %) · Impresa 59 € (≈ 45 %) · Premium tapa dura 89 € (≈ 60 %).
Derecha, escenario: "0,05 % de los ~22 M de compradores de libros en España = ~11.000 novelas/año ≈ 650.000 €" + "LatAm y B2B (bodas, jubilaciones, regalo de empresa) aparte".
Nota al pie: "Márgenes estimados; coste IA extrapolado de tiradas reales."

9. POR QUÉ NOSOTROS (6:00–6:40)
Título: "Qaracter: IA seria para productos que emocionan"
Mapa con presencia: España, EE. UU., México, Brasil, Argentina, Reino Unido, Polonia.
Tres puntos: IA en entornos regulados (banca y seguros) · ISO 27001 / 9001 · Piloto funcional ya construido.

10. CIERRE Y PETICIÓN (6:40–7:00)
Fondo azul #1E2D3D, frase grande en Literata: "Esta Navidad, regala una historia que solo existe para una persona."
Llamada a la acción en naranja: "Hagamos juntos el piloto: la primera novela, para alguien a quien quieras sorprender."
Espacio editable para la petición concreta [INVERSIÓN / ACUERDO / PILOTO] y datos de contacto [CONTACTO].

REGLAS
- Una idea por diapositiva, máximo ~25 palabras de texto visible (el resto en notas del orador).
- Cifras siempre con su fuente en pie pequeño.
- Sin imágenes de personas reales ni logotipos de terceros; representa a los competidores solo con su nombre en texto.
- Accesible: contraste AA, el color nunca es la única señal.
```

---

## Fuentes

- [FGEE · Comercio Interior del Libro 2025 (avance)](https://federacioneditores.org/wp-content/uploads/2026/06/Avance-Resultados-Comercio-Interior-2025-110626.pdf) · [resumen Editores Madrid](https://editoresmadrid.org/comercio-interior-del-libro-2025-el-sector-editorial-crece-por-duodecimo-ano-consecutivo-y-alcanza-los-3-138-millones-de-euros/)
- [AEA · Mercado del libro 2025 (datos GfK)](https://www.aea.es/el-mercado-del-libro-en-espana-marca-un-nuevo-record-en-2025-con-cerca-de-1-250-millones-de-euros/)
- [Barómetro de Hábitos de Lectura 2025 (Todoliteratura)](https://www.todoliteratura.es/noticia/62162/actualidad/la-lectura-por-ocio-sigue-creciendo-en-espana-el-662--de-la-poblacion-lee-libros-en-su-tiempo-libre.html) · [Ministerio de Cultura](https://www.cultura.gob.es/en/actualidad/2026/01/260122-barometro-lectura-2025.html)
- [Grand View Research · Books Market](https://www.grandviewresearch.com/industry-analysis/books-market)
- [Business Research Insights · Personalized Children Books Market](https://www.businessresearchinsights.com/market-reports/personalized-children-books-market-119694)
- [Technavio · Personalized Gifts Market](https://www.prnewswire.com/news-releases/personalized-gifts-market-to-grow-by-usd-10-76-billion-2025-2029-driven-by-new-product-innovations-report-on-how-ai-is-driving-market-transformation---technavio-302354898.html)
- [Penguin Random House adquiere Wonderbly](https://global.penguinrandomhouse.com/announcements/prh-acquires-wonderbly-one-of-the-uks-fastest-growing-independent-publishers-and-leader-in-personalized-gift-books/)
- [Cuentoslandia · regalos pareja](https://www.cuentoslandia.com/regalos-pareja) · [GiftBookStory](https://www.giftbookstory.com/ai-written-book-gift) · [Book by Anyone](https://www.bookbyanyone.com/us)
- [Amazon KDP · gasto de impresión tapa blanda](https://kdp.amazon.com/es_ES/help/topic/G201834340)
- [AI Act · artículo 50](https://artificialintelligenceact.eu/transparency-rules-article-50/)
- [Qaracter](https://www.qaracter.com/)
- Repositorio Story-Maker, rama `v2-oneshot`: `docs/architecture.md`, `docs/verification.md`, `backend/commons/types/length.py`, `backend/evals/results/adversarial-02.md`, `.claude/handoff/2026-09-24.md`, `frontend/commons/brand/BRAND.md`
