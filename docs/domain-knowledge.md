# domain-knowledge.md

> Documentación de dominio · ver [`../AGENTS.md`](../AGENTS.md) para el índice completo.
> Relacionados: [definitions](definitions.md) · [architecture](architecture.md) · [verification](verification.md)

Representación visual de la ontología definida en `definitions.md`. Cada diagrama responde a una pregunta concreta sobre el dominio. Los identificadores entre corchetes remiten al glosario.

Índice:

1. Mapa maestro de capas
2. Árbol estructural de la obra
3. Modelo relacional del núcleo
4. Anatomía de la escena
5. Árbol de personaje
6. Árbol del mundo
7. Árbol del subdominio deportivo
8. Cronología y estado
9. Árbol de poética y estilo
10. Árbol de canon y continuidad
11. Ciclo setup → payoff
12. Árbol de contexto
13. Composición del paquete de contexto
14. Árbol de calidad
15. Ciclo de vida de un capítulo
16. Mapa de modos de fallo

---

## 1. Mapa maestro de capas

Vista de conjunto. Tres bloques: lo que se cuenta, cómo se cuenta y cómo se controla.

```mermaid
graph TD
  ONT["Ontología del dominio"]

  ONT --> A["A. Qué existe en la ficción"]
  ONT --> B["B. Cómo se expresa"]
  ONT --> C["C. Cómo se produce y controla"]

  A --> EST["EST · Estructura narrativa"]
  A --> PER["PER · Agentes narrativos"]
  A --> MUN["MUN · Mundo"]
  A --> DEP["DEP · Subdominio deportivo"]

  B --> POE["POE · Poética y estilo"]
  B --> CAN["CAN · Canon y continuidad"]

  C --> CTX["CTX · Contexto"]
  C --> CAL["CAL · Calidad"]
  C --> PRO["PRO · Proceso"]

  DEP -.perfil de.-> MUN
  DEP -.perfil de.-> PER
  CAN -.restringe.-> EST
  CTX -.alimenta.-> PRO
  CAL -.controla.-> PRO
```

El subdominio deportivo es un **perfil sustituible**: cambiarlo por otro género no obliga a rehacer el resto.

---

## 2. Árbol estructural de la obra

Descomposición del texto, de universo a beat.

```mermaid
graph TD
  UNI["Universo · EST-01"] --> SAG["Saga · EST-02"]
  SAG --> OBR["Obra · EST-03"]
  OBR --> PAR["Parte · EST-04"]
  PAR --> ACT["Acto · EST-05"]
  ACT --> CAP["Capítulo · EST-07"]
  CAP --> SEC["Secuencia · EST-09"]
  SEC --> ESC["Escena · EST-08"]
  ESC --> BEA["Beat · EST-10"]

  OBR -.atravesada por.-> ARC["Arco · EST-06"]
  OBR -.atravesada por.-> LIN["Línea argumental · EST-11"]
  ARC -.se realiza en.-> ESC
  LIN -.se realiza en.-> ESC

  OBR --> OUT["Escaleta · EST-12"]
  OUT -.planifica.-> ESC
```

Punto clave del diagrama: **arcos y líneas no son contenedores, son trayectorias transversales**. Modelarlos como jerarquía es el primer error de diseño habitual.

---

## 3. Modelo relacional del núcleo

Cardinalidades entre las entidades que sí se persisten.

```mermaid
erDiagram
  OBRA ||--o{ CAPITULO : contiene
  CAPITULO ||--|{ ESCENA : contiene
  OBRA ||--o{ ARCO : desarrolla
  ARCO }o--o{ ESCENA : se_realiza_en
  ESCENA }o--|| PERSONAJE : tiene_pov
  ESCENA }o--o{ PERSONAJE : presenta
  ESCENA }o--|| LUGAR : ocurre_en
  ESCENA ||--o{ EVENTO : produce
  EVENTO }o--o{ ENTIDAD : modifica
  EVENTO ||--|| HECHO_CANONICO : genera
  PERSONAJE ||--o{ ARCO_PERSONAJE : recorre
  PERSONAJE }o--o{ PERSONAJE : se_relaciona_con
  PERSONAJE }o--o{ HECHO_CANONICO : conoce
  PERSONAJE }o--|| FACCION : pertenece_a
  SETUP ||--o| PAYOFF : salda
  ESCENA ||--o{ SETUP : planta
  ESCENA ||--o{ PAYOFF : cobra
  ENCUENTRO ||--|| RESULTADO : produce
  ENCUENTRO }o--|| COMPETICION : pertenece_a
  RESULTADO }o--|| CLASIFICACION : actualiza
```

La relación `PERSONAJE }o--o{ HECHO_CANONICO : conoce` (PER-10) es la que más incoherencias previene y la que casi nadie modela.

---

## 4. Anatomía de la escena

Unidad mínima que el sistema genera y evalúa.

```mermaid
graph LR
  ESC["Escena · EST-08"]

  ESC --> ID["Identidad"]
  ID --> I1["Capítulo y posición"]
  ID --> I2["POV · PER-13"]
  ID --> I3["Lugar · MUN-01"]
  ID --> I4["Instante de mundo · MUN-05"]

  ESC --> FUN["Función dramática"]
  FUN --> F1["Tipo de función · EST-14"]
  FUN --> F2["Cambio de valor · EST-13"]
  FUN --> F3["Objetivo del POV en la escena"]
  FUN --> F4["Obstáculo"]

  ESC --> CNT["Contenido"]
  CNT --> C1["Elenco presente · PER-16"]
  CNT --> C2["Beats · EST-10"]
  CNT --> C3["Información revelada"]
  CNT --> C4["Setups plantados · CAN-06"]
  CNT --> C5["Payoffs cobrados · CAN-07"]

  ESC --> SAL["Salida"]
  SAL --> S1["Delta canónico · CAN-11"]
  SAL --> S2["Transición · EST-15"]
  SAL --> S3["Elipsis hasta la siguiente · EST-16"]

  ESC --> RES["Restricciones"]
  RES --> R1["Longitud objetivo"]
  RES --> R2["Registro y distancia · POE-05, PER-15"]
  RES --> R3["Prohibiciones · POE-12"]
```

Una escena bien especificada así es generable sin ambigüedad y evaluable sin lectura completa del capítulo.

---

## 5. Árbol de personaje

```mermaid
graph TD
  PER["Personaje · PER-01"]

  PER --> IDT["Identidad"]
  IDT --> ID1["Nombre canónico y alias"]
  IDT --> ID2["Datos biográficos"]
  IDT --> ID3["Rasgos físicos estables"]

  PER --> PSI["Motor interno"]
  PSI --> P1["Deseo · PER-03"]
  PSI --> P2["Necesidad · PER-04"]
  PSI --> P3["Herida · PER-05"]
  PSI --> P4["Creencia limitante"]
  PSI --> P5["Valores y línea roja"]

  PER --> ARQ["Arco · PER-06"]
  ARQ --> A1["Estado inicial"]
  ARQ --> A2["Grietas"]
  ARQ --> A3["Crisis"]
  ARQ --> A4["Decisión"]
  ARQ --> A5["Estado final"]

  PER --> VOZ["Voz · PER-07"]
  VOZ --> V1["Idiolecto · PER-08"]
  VOZ --> V2["Longitud y sintaxis típicas"]
  VOZ --> V3["Temas recurrentes"]
  VOZ --> V4["Lo que nunca dice"]

  PER --> EST2["Estado variable en t"]
  EST2 --> E1["Competencia · PER-09"]
  EST2 --> E2["Conocimiento · PER-10"]
  EST2 --> E3["Relaciones vigentes · PER-11"]
  EST2 --> E4["Ubicación y posesiones"]
  EST2 --> E5["Estado físico · DEP-13"]

  PER --> FUN2["Función"]
  FUN2 --> N1["Rol actancial por arco · PER-02"]
  FUN2 --> N2["Facción · PER-12"]
```

Nótese la separación entre **rasgos estables** e **estado variable en t**. Solo el segundo bloque necesita proyectarse por instante; el primero se cachea una vez.

---

## 6. Árbol del mundo

```mermaid
graph TD
  MUN["Mundo · MUN"]

  MUN --> ESP["Espacio"]
  ESP --> L1["Lugar · MUN-01"]
  ESP --> L2["Geografía relativa"]
  ESP --> L3["Textura sensorial · MUN-09"]

  MUN --> SOC["Sociedad"]
  SOC --> S1["Institución · MUN-03"]
  SOC --> S2["Facción · PER-12"]
  SOC --> S3["Normas sociales"]
  SOC --> S4["Opinión pública · DEP-16"]

  MUN --> REG["Reglas"]
  REG --> R1["Regla del mundo · MUN-04"]
  REG --> R2["Reglamento deportivo · DEP-02"]
  REG --> R3["Economía · DEP-17"]

  MUN --> TMP["Tiempo"]
  TMP --> T1["Cronología · MUN-05"]
  TMP --> T2["Eventos históricos · MUN-07"]
  TMP --> T3["Calendario competitivo · DEP-05"]

  MUN --> MAT["Materia"]
  MAT --> M1["Objeto significante · MUN-02"]
  MAT --> M2["Léxico del mundo · MUN-08"]
```

---

## 7. Árbol del subdominio deportivo

```mermaid
graph TD
  DEP["Épica deportiva · DEP"]

  DEP --> MAR["Marco competitivo"]
  MAR --> C1["Disciplina · DEP-01"]
  MAR --> C2["Reglamento · DEP-02"]
  MAR --> C3["Competición · DEP-03"]
  MAR --> C4["Temporada · DEP-04"]
  MAR --> C5["Jornada · DEP-05"]

  DEP --> ENC["Encuentro · DEP-06"]
  ENC --> E1["Previa y presión"]
  ENC --> E2["Planteamiento táctico · DEP-11"]
  ENC --> E3["Desarrollo y giro"]
  ENC --> E4["Momento cumbre · DEP-18"]
  ENC --> E5["Resultado · DEP-07"]
  ENC --> E6["Consecuencias y vestuario"]

  DEP --> ACT2["Actores"]
  ACT2 --> A1["Plantilla · DEP-09"]
  ACT2 --> A2["Cuerpo técnico · DEP-10"]
  ACT2 --> A3["Rival · DEP-15"]
  ACT2 --> A4["Afición y prensa · DEP-16"]
  ACT2 --> A5["Entorno personal"]

  DEP --> CUE["Cuerpo y límite"]
  CUE --> B1["Estado físico · DEP-13"]
  CUE --> B2["Lesión · DEP-14"]
  CUE --> B3["Edad deportiva"]
  CUE --> B4["Competencia técnica · PER-09"]

  DEP --> NUM["Estado derivado"]
  NUM --> D1["Clasificación · DEP-08"]
  NUM --> D2["Estadística · DEP-12"]

  DEP --> DOB["Doble arco · DEP-20"]
  DOB --> G1["Arco competitivo: ¿gana?"]
  DOB --> G2["Arco interno: ¿cambia?"]
```

Los nodos de **estado derivado** nunca se narran de memoria: se calculan y se inyectan como dato.

---

## 8. Cronología y estado

Cómo se pasa de eventos a "qué es verdad ahora".

```mermaid
graph LR
  subgraph Fuente
    EV1["Evento · MET-05"]
    EV2["Evento"]
    EV3["Evento"]
  end

  EV1 --> LOG["Registro cronológico append-only"]
  EV2 --> LOG
  EV3 --> LOG

  LOG --> PROY["Proyección"]

  PROY --> ST1["Estado del mundo en t · MUN-10"]
  PROY --> ST2["Estado de personaje en t"]
  PROY --> ST3["Conocimiento por personaje en t · PER-10"]
  PROY --> ST4["Clasificación y estadísticas · DEP-08, DEP-12"]
  PROY --> ST5["Setups abiertos · CAN-08"]

  ST1 --> CTXP["Paquete de contexto · CTX-03"]
  ST2 --> CTXP
  ST3 --> CTXP
  ST4 --> CTXP
  ST5 --> CTXP
```

Principio: **los eventos son la verdad, el estado es una vista**. Permite reconstruir el mundo en cualquier punto sin ambigüedad, que es justo lo que hace falta para escribir analepsis sin romper nada.

---

## 9. Árbol de poética y estilo

```mermaid
graph TD
  POE["Poética · POE"]

  POE --> SIG["Significado"]
  SIG --> S1["Tema · POE-01"]
  SIG --> S2["Motivo · POE-02"]
  SIG --> S3["Símbolo · POE-03"]

  POE --> SUP["Superficie"]
  SUP --> U1["Tono · POE-04"]
  SUP --> U2["Registro · POE-05"]
  SUP --> U3["Guía de estilo · POE-06"]
  SUP --> U4["Tratamiento del diálogo y subtexto · POE-09"]

  POE --> MOV["Movimiento"]
  MOV --> M1["Ritmo · POE-07"]
  MOV --> M2["Densidad · POE-08"]
  MOV --> M3["Mostrar vs contar · POE-10"]

  POE --> CTR["Control de degradación"]
  CTR --> D1["Tic de modelo · POE-11"]
  CTR --> D2["Lista de proscripción · POE-12"]
  CTR --> D3["Huella estilística · POE-13"]
  CTR --> D4["Autosimilitud · POE-14"]
```

La rama de control de degradación no existe en la teoría literaria clásica. Es propia de la generación automática y hay que modelarla explícitamente o el estilo se aplana hacia el capítulo 15.

---

## 10. Árbol de canon y continuidad

```mermaid
graph TD
  CAN["Canon · CAN-01"]

  CAN --> HEC["Hechos"]
  HEC --> H1["Hecho canónico · CAN-02"]
  HEC --> H2["Procedencia · MET-09"]
  HEC --> H3["Vigencia · MET-07"]

  CAN --> BIB["Biblia de la obra · CAN-03"]
  BIB --> B1["Fichas de personaje"]
  BIB --> B2["Fichas de mundo"]
  BIB --> B3["Guía de estilo"]
  BIB --> B4["Escaleta"]
  BIB --> B5["Reglamento del subdominio"]

  CAN --> INT["Integridad"]
  INT --> I1["Continuidad · CAN-04"]
  INT --> I2["Contradicción · CAN-05"]
  INT --> I3["Retcon controlado · CAN-10"]

  CAN --> PRM["Promesas"]
  PRM --> P1["Setup · CAN-06"]
  PRM --> P2["Prefiguración · CAN-09"]
  PRM --> P3["Payoff · CAN-07"]
  PRM --> P4["Deuda narrativa · CAN-08"]

  CAN --> EVO["Evolución"]
  EVO --> V1["Delta canónico · CAN-11"]
  EVO --> V2["Congelación · CAN-12"]

  I2 --> T1["De hecho"]
  I2 --> T2["Temporal"]
  I2 --> T3["De conocimiento"]
  I2 --> T4["De capacidad"]
  I2 --> T5["De estado físico"]
  I2 --> T6["De nombre o léxico"]
```

---

## 11. Ciclo setup → payoff

La deuda narrativa como máquina de estados.

```mermaid
stateDiagram-v2
  [*] --> Planificado: aparece en la escaleta
  Planificado --> Plantado: se escribe la escena que lo siembra
  Plantado --> Reforzado: reaparición intermedia
  Reforzado --> Reforzado: nueva reaparición
  Plantado --> Cobrado: llega el payoff
  Reforzado --> Cobrado: llega el payoff
  Cobrado --> [*]
  Plantado --> Vencido: pasa el punto límite sin cobrarse
  Reforzado --> Vencido: pasa el punto límite sin cobrarse
  Vencido --> Cobrado: rescate en revisión
  Vencido --> Descartado: se elimina la siembra
  Descartado --> [*]
  Planificado --> Descartado: se decide no sembrarlo
```

Todo setup en estado `Plantado`, `Reforzado` o `Vencido` al llegar al desenlace es deuda narrativa pendiente (CAN-08).

---

## 12. Árbol de contexto

Dos techos de 100.000 tokens que no son el mismo: la ventana física de una llamada (CTX-01) y el techo de concurrencia del sistema (CTX-20), que suma todo lo que está en vuelo a la vez. Dentro de una llamada, la ocupación operativa (CTX-18) que se permite usar es aún menor: el límite útil lo marca la atención del modelo, no el del proveedor.

```mermaid
graph TD
  CTX["Ingeniería de contexto · CTX-04"]

  CTX --> LIM["Límites"]
  LIM --> L1["Ventana física: 100.000 tokens · CTX-01"]
  LIM --> L2["Presupuesto · CTX-02"]
  LIM --> L3["Ocupación operativa · CTX-18"]
  LIM --> L4["Desbordamiento y compactación · CTX-19"]
  LIM --> L5["Sesgo de recencia · CTX-16"]
  LIM --> L6["Techo de concurrencia · CTX-20"]

  CTX --> FUE["Fuentes de material"]
  FUE --> F1["Canon estructurado · CAN-03"]
  FUE --> F2["Estado en t · MUN-10"]
  FUE --> F3["Resumen jerárquico · CTX-06"]
  FUE --> F4["Ventana literal reciente · CTX-07"]
  FUE --> F5["Recuperación híbrida · CTX-09"]

  CTX --> TRA["Transformaciones"]
  TRA --> T1["Ficha compacta · CTX-05"]
  TRA --> T2["Compactación · CTX-10"]
  TRA --> T3["Aislamiento · CTX-11"]
  TRA --> T4["Anclas · CTX-17"]

  CTX --> PAT["Patologías"]
  PAT --> D1["Deriva · CTX-12"]
  PAT --> D2["Envenenamiento · CTX-13"]
  PAT --> D3["Distracción · CTX-14"]
  PAT --> D4["Conflicto · CTX-15"]
```

---

## 13. Composición del paquete de contexto

Qué entra en la llamada que escribe una escena, y en qué orden.

```mermaid
graph TD
  ENT["Entrada: escena a escribir"] --> SEL["Selector"]

  SEL --> Q1["Consulta estructurada al canon"]
  SEL --> Q2["Búsqueda semántica en prosa previa"]
  SEL --> Q3["Búsqueda léxica por nombres propios"]
  SEL --> Q4["Consulta al grafo de entidades"]

  Q1 --> FUS["Fusión y deduplicación"]
  Q2 --> FUS
  Q3 --> FUS
  Q4 --> FUS

  FUS --> PRI["Priorización por presupuesto · CTX-02"]
  PRI --> COMP["Compactación de excedente · CTX-10"]
  COMP --> ORD["Ordenación"]

  ORD --> PK["Paquete de contexto · CTX-03"]

  PK --> B1["1 · Ancla de estilo e invariantes · CTX-17"]
  PK --> B2["2 · Fichas del elenco activo · CTX-05"]
  PK --> B3["3 · Estado del mundo en t · MUN-10"]
  PK --> B4["4 · Conocimiento del POV · PER-10"]
  PK --> B5["5 · Resúmenes jerárquicos · CTX-06"]
  PK --> B6["6 · Prosa literal de la escena anterior · CTX-07"]
  PK --> B7["7 · Recuperación puntual · CTX-08"]
  PK --> B8["8 · Setups abiertos relevantes · CAN-08"]
  PK --> B9["9 · Lista de proscripción · POE-12"]
  PK --> B10["10 · Muestra modélica de voz"]
  PK --> B11["11 · Especificación de la escena"]

  B11 --> GEN["Llamada de generación"]
```

Los once bloques y su orden son los de [`architecture.md`](architecture.md) §4.3, que es donde viven sus presupuestos en tokens. La especificación de la escena va **al final** por CTX-16. Las anclas van al principio porque deben sobrevivir a la compactación.

---

## 14. Árbol de calidad

```mermaid
graph TD
  CAL["Calidad · CAL"]

  CAL --> DIM["Dimensiones · CAL-01"]
  DIM --> X1["Continuidad factual y temporal"]
  DIM --> X2["Caracterización y voz"]
  DIM --> X3["Integridad estructural"]
  DIM --> X4["Tensión, ritmo y densidad"]
  DIM --> X5["Fidelidad de estilo"]
  DIM --> X6["Verosimilitud deportiva · DEP-19"]
  DIM --> X7["No redundancia"]
  DIM --> X8["Diálogo y subtexto"]
  DIM --> X9["Resonancia temática"]
  DIM --> X10["Cumplimiento del brief"]

  CAL --> MEC["Mecanismos"]
  MEC --> M1["Verificador determinista · CAL-03"]
  MEC --> M2["Juez LLM con rúbrica · CAL-04"]
  MEC --> M3["Conjunto dorado y jurado · CAL-10, CAL-11"]

  CAL --> GOB["Gobierno"]
  GOB --> G1["Rúbrica · CAL-02"]
  GOB --> G2["Umbral · CAL-09"]
  GOB --> G3["Puerta de calidad · CAL-07"]

  CAL --> REM["Remediación"]
  REM --> R1["Defecto y severidad · CAL-05, CAL-06"]
  REM --> R2["Regeneración dirigida · CAL-08"]
  REM --> R3["Arbitraje y replanificación · PRO-10, PRO-12"]
  REM --> R4["Cuarentena al agotar reintentos · CAL-12, CAL-13"]

  X1 --> M1
  X6 --> M1
  X7 --> M1
  X10 --> M1
  X4 --> M2
  X8 --> M2
  X9 --> M2
  X2 --> M1
  X2 --> M2
```

---

## 15. Ciclo de vida de un capítulo

```mermaid
stateDiagram-v2
  [*] --> Planificado
  Planificado --> Contextualizado: se ensambla el paquete · CTX-03
  Contextualizado --> Borrador: generación · PRO-06
  Borrador --> Verificado: verificadores deterministas · CAL-03
  Verificado --> Borrador: defectos S1 detectados
  Verificado --> Evaluado: juez con rúbrica · CAL-04
  Evaluado --> Revisión: defectos S2 o S3
  Revisión --> Verificado: regeneración dirigida · CAL-08
  Evaluado --> PaseDeEstilo: supera umbrales
  PaseDeEstilo --> Verificado: reverificación tras el pase
  Evaluado --> Cuarentena: reintentos agotados · CAL-12
  Cuarentena --> Replanificado: replanificación automática · PRO-12
  Replanificado --> Contextualizado
  PaseDeEstilo --> Integrado: todas las puertas superadas
  Integrado --> Congelado: delta canónico integrado · CAN-11
  Congelado --> [*]
  Congelado --> Reabierto: retcon arbitrado · CAN-10, PRO-10
  Reabierto --> Revisión
```

El paso `Integrado → Congelado` es el único que modifica el canon. Todo lo anterior trabaja sobre material provisional.

---

## 16. Mapa de modos de fallo

Qué se rompe, por qué y dónde se ataca.

```mermaid
graph LR
  subgraph Síntoma
    F1["Contradice un hecho anterior"]
    F2["Un personaje sabe algo imposible"]
    F3["El estilo se aplana con los capítulos"]
    F4["Todos hablan igual"]
    F5["Repite imágenes y frases"]
    F6["Ritmo uniforme, sin clímax"]
    F7["Promesas sin cobrar"]
    F8["Resultado o estadística imposible"]
    F9["Ignora parte de la instrucción"]
  end

  F1 --> C1["Canon ausente del contexto o desactualizado"]
  F2 --> C2["No se modela el conocimiento por personaje"]
  F3 --> C3["Deriva · CTX-12"]
  F4 --> C4["Idiolecto no especificado ni verificado"]
  F5 --> C5["Autosimilitud · POE-14"]
  F6 --> C6["Ritmo no planificado por escena"]
  F7 --> C7["Deuda narrativa no rastreada"]
  F8 --> C8["Estado derivado narrado de memoria"]
  F9 --> C9["Distracción por exceso de contexto · CTX-14"]

  C1 --> S1["Recuperación híbrida + estado en t"]
  C2 --> S2["Proyección de conocimiento · PER-10"]
  C3 --> S3["Anclas fijas + huella estilística"]
  C4 --> S4["Ficha de voz en contexto + juez de voz"]
  C5 --> S5["Lista de proscripción dinámica · POE-12"]
  C6 --> S6["Curva de tensión en la escaleta"]
  C7 --> S7["Registro de setups · sección 11"]
  C8 --> S8["Cálculo determinista e inyección como dato"]
  C9 --> S9["Presupuesto de contexto + compactación"]
```

Cada solución de la columna derecha corresponde a un componente concreto en [`architecture.md`](architecture.md) y a un método de verificación con ID en [`verification.md`](verification.md).
