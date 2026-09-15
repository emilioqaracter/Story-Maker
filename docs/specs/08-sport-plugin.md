# Spec 08: Plugin de deporte

**Decisión D5:** fútbol es la primera y única implementación, pero el deporte
se aísla tras un contrato para no cablear sus reglas en el núcleo.

## Contrato

Un plugin de deporte aporta cuatro cosas, y nada más:

```
sports/football/
├── plugin.yaml          metadatos y vocabulario
├── calendar.yaml        estructura de temporada (afecta a la validación temporal)
├── plausibility.md      criterios para la lente L2 del crítico
└── lexicon.yaml         jerga por país y época + anacronismos del deporte
```

### 1. `plugin.yaml`
```yaml
sport: football
roles: [portero, defensa, centrocampista, delantero, entrenador, utilero]
positions_matter: true
team_size: 11
match_duration_min: 90
```

### 2. `calendar.yaml` — alimenta reglas temporales
```yaml
season:
  runs: [agosto, junio]        # hemisferio norte; configurable
  match_cadence_days: 7        # ritmo habitual de partido
  windows:
    - { type: mercado_fichajes, months: [7, 8, 1] }
    - { type: parón_selecciones, cadence: bimestral }

recovery_times_days:           # usado por la regla C04
  rotura_fibrilar: [21, 40]
  ligamento_cruzado: [180, 270]
  esguince_tobillo: [10, 25]
```

> Esto convierte plausibilidad médica en una regla **calculable**: si la escena
> devuelve a Marco al campo 6 días después de una rotura fibrilar, es ERROR, no opinión.

### 3. `plausibility.md`
Criterios en lenguaje natural para la lente L2 del crítico: decisiones tácticas,
jerarquía del vestuario, relación con prensa y directiva, cultura del club.

### 4. `lexicon.yaml`
```yaml
country: argentina
era: 1990
preferred: [pelota, arquero, botines, wing]
avoid:     [balón, portero, botas]        # registro peninsular, rompe la voz
anachronisms: [VAR, quinto cambio, sustitución por conmoción, gol de oro]
```

`anachronisms` se fusiona con `premise.anachronism_blocklist` para la regla P01.

## Qué NO conoce el núcleo

El núcleo (context store, validadores T/C, ciclo, crítico L1/L3/L4) no contiene
la palabra "fútbol" en ninguna parte. Añadir boxeo o ciclismo = añadir un
directorio, sin tocar el motor.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial (decisión D5). Contrato de 4 archivos del plugin; tiempos de recuperación como regla calculable para C04. |
