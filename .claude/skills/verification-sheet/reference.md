# Referencias canónicas de los métodos

Un enlace por método, a la **explicación de la metodología**, nunca a la página de un producto. Se usan al citar un método en `verification.md`.

Los números son los de `SKILL.md` §3 y se corresponden con los IDs `VER-01` a `VER-18`.

## Verificación de producto

| # | Método | Referencia |
|---|---|---|
| 1 | Type checking | [Type system — Wikipedia](https://en.wikipedia.org/wiki/Type_system) |
| 2 | Static analysis / SAST | [Static program analysis — Wikipedia](https://en.wikipedia.org/wiki/Static_program_analysis) |
| 3 | Symbolic execution | [Symbolic execution — Wikipedia](https://en.wikipedia.org/wiki/Symbolic_execution) |
| 4 | Formal verification | [Formal verification — Wikipedia](https://en.wikipedia.org/wiki/Formal_verification) |
| 5 | Unit / integration testing | [Unit testing — Wikipedia](https://en.wikipedia.org/wiki/Unit_testing) |
| 6 | Property-based testing | [QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs — Claessen y Hughes, 2000](https://dl.acm.org/doi/10.1145/351240.351266) |
| 7 | Mutation testing | [Mutation testing — Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing) |
| 8 | Contract testing | [Contract Test — Martin Fowler](https://martinfowler.com/bliki/ContractTest.html) |

## Verificación de proceso

| # | Método | Referencia |
|---|---|---|
| 9 | Runtime observability / tracing | [Observability primer — OpenTelemetry](https://opentelemetry.io/docs/concepts/observability-primer/) |
| 10 | Evals | [Holistic Evaluation of Language Models (HELM) — Liang et al., 2022](https://arxiv.org/abs/2211.09110) |
| 11 | Sandboxed execution | [Sandbox (computer security) — Wikipedia](https://en.wikipedia.org/wiki/Sandbox_(computer_security)) |
| 12 | Guardrails | [AI Risk Management Framework — NIST](https://www.nist.gov/itl/ai-risk-management-framework) |
| 13 | Human-in-the-loop review | [Human-in-the-loop — Wikipedia](https://en.wikipedia.org/wiki/Human-in-the-loop) |
| 14 | Multi-agent verification | [AI Safety via Debate — Irving, Christiano y Amodei, 2018](https://arxiv.org/abs/1805.00899) |
| 15 | CI/CD integration | [Continuous integration — Wikipedia](https://en.wikipedia.org/wiki/Continuous_integration) |
| 16 | Progressive rollout | [Feature toggle — Wikipedia](https://en.wikipedia.org/wiki/Feature_toggle) |
| 17 | Red-teaming / adversarial testing | [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) |
| 18 | Model checking | [Model checking — Wikipedia](https://en.wikipedia.org/wiki/Model_checking) |

## Esquema de clasificación

| Esquema | Referencia |
|---|---|
| T / A / I / D / U | [Verification and validation — Wikipedia](https://en.wikipedia.org/wiki/Verification_and_validation) |

## Nota de la fuente

Property-based testing y evals **no tienen una referencia fundacional neutral** como sí la tiene la verificación formal. Los enlaces de arriba apuntan al trabajo que introdujo o formalizó cada metodología —QuickCheck para el primero, HELM para el segundo—, que es una elección entre varias posibles, no la única.
