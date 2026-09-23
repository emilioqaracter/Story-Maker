"""Verificacion formal de la cronologia con Lean 4. `specs/srs-backend-v4.md` §4.6, T43.

`generate` exporta la cronologia del canon a un fichero Lean; `check.run_lean`
lo compila con `lake build` y dice que teorema fallo y con que filas. El
proyecto Lake, con los tipos y las cuatro invariantes, vive en `lean/`.
"""
