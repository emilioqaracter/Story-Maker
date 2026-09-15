# Spec 07: Retcon y revalidación en cascada

**Decisión D7:** se permite modificar canon ya aprobado, con propagación automática
del impacto. Es la función que más trabajo salva y la más delicada de implementar.

## 1. El problema

Cambiar `marco.birth_date` de 1962 a 1965 invalida silenciosamente cada escena
donde se mencionó su edad, cada referencia a su debut y cada cálculo derivado.
Sin cascada, el sistema queda coherente en el estado e incoherente en la prosa.

## 2. Grafo de dependencias

Esto es lo que hace posible la cascada. `LEDGER_WRITER` lo mantiene al aprobar
cada escena: registra de qué hechos **dependió** el DRAFTER, no solo cuáles estableció.

```
                     marco.birth_date
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
          F003            F014            F027
      "debuta a          "cumple         "el mayor
       los 19"           28 el 14-mar"    del vestuario"
            │               │                │
            ▼               ▼                ▼
          S002            S007             S031
            │               │
            ▼               ▼
          cap.1           cap.3
```

Cada escena guarda:

```yaml
  - id: S007
    depends_on: [marco.immutables.birth_date, F014, R001]
    establishes: [F014]
```

## 3. Flujo del retcon

```
  Humano edita canon (o LEDGER_WRITER detecta contradicción)
                    │
                    ▼
        ┌─────────────────────────┐
        │  IMPACT ANALYZER        │  recorre el grafo hacia abajo
        └───────────┬─────────────┘
                    ▼
     ┌──────────────────────────────────────┐
     │ INFORME DE IMPACTO                   │
     │  afectadas: S002, S007, S031         │
     │  capítulos tocados: 1, 3, 8          │
     │  hechos invalidados: F003, F014      │
     │  coste estimado de regeneración: N   │
     └───────────────┬──────────────────────┘
                     ▼
              ╔═══════════════╗
              ║  GATE HUMANO  ║  aprobar / descartar el cambio
              ╚═══════╤═══════╝
                      ▼ aprobado
       escenas afectadas -> estado `stale`
                      │
                      ▼
       ┌──────────────────────────────┐
       │ Para cada escena stale:      │
       │  1. VALIDATOR (¿sigue rota?) │  <- muchas pasan sin tocar nada
       │  2. si rota -> REVISER       │     (revisión quirúrgica, NO reescritura)
       │  3. VALIDATOR + CRITIC       │
       │  4. LEDGER_WRITER -> commit  │
       └──────────────────────────────┘
```

## 4. Reglas

| Regla | Motivo |
|---|---|
| El informe de impacto **siempre** precede al cambio | el usuario debe ver el coste antes de pagarlo |
| Una escena `stale` se **revisa**, no se regenera | regenerar de cero pierde prosa buena y cambia el tono |
| Nada se pierde: rama de git `retcon/<id>` | si la cascada empeora la novela, se descarta entera |
| Si el retcon toca `premise.lock.yaml` | revalidación **completa** de la obra, no parcial |
| Escenas `stale` que el validador aprueba sin cambios | se marcan `approved` de nuevo sin gastar tokens |

## 5. Modo `audit`

Ejecuta el validador completo sobre toda la obra sin generar nada. Debe poder
lanzarse en cualquier momento; es el chequeo de salud del proyecto y la forma
de detectar drift acumulado.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial (decisión D7). Grafo de dependencias, flujo de impacto con gate humano, reglas de cascada y modo audit. |
