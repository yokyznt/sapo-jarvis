# Contribuir

- Abre un issue antes de cambios grandes.
- El código va **sin comentarios** (ni `//`, ni `#`, ni docstrings): nombres claros en su lugar.
- Corre las pruebas antes del PR: `cd brain && uv run pytest`, `cd settings && uv run pytest`, `cd pc && dotnet build` sin advertencias.
- Si arreglas un bug, agrega una prueba que falle sin tu arreglo y anótalo en la tabla de bugs de `docs/plan/`.
- Nunca subas llaves ni datos personales.
