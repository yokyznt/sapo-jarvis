# Preferencias del Sapo

Ventana de ajustes de Sapo-Jarvis (`SapoPreferencias.exe`). Edita el `config.json` compartido descrito en [docs/config.md](../docs/config.md) y guarda la key de Gemini cifrada con DPAPI en `secrets.json`.

- Interfaz HTML/CSS/JS local (sin CDN) dentro de pywebview con WebView2, que ya viene en Windows 11.
- Guarda solo al cambiar algo, con escritura atómica. Respeta las claves que no conoce y las secciones de otros programas.
- Modo claro u oscuro según Windows.
- No pide permisos de administrador. El inicio automático usa `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, valor `Sapo`.

## Pestañas

| Pestaña | Qué ajusta |
|---|---|
| Sapo | diseño (galería), tamaño, energía, pantalla, soltar del nenúfar, sonidos y volumen |
| Cerebro | proveedor Gemini/Local, key de Gemini (guardar, probar, borrar), personalidad, minutos entre comentarios, atención, visión y lista negra |
| Voz | activar o desactivar, palabra clave, motor, voz, tono, velocidad, micrófono y altavoz |
| Inicio | arrancar con Windows y el comando que se ejecuta |
| Acerca de | versión, licencia, repositorio y carpeta de configuración |

## Desarrollo

Requisitos: [uv](https://docs.astral.sh/uv/). Usa Python 3.12.

```bash
cd settings
uv sync
uv run python run.py
uv run pytest
```

Variables de entorno:

- `SAPO_HOME`: carpeta de `config.json` y `secrets.json`. Si no se define, se usa `%APPDATA%\Sapo`. Sirve para hacer pruebas sin tocar tu configuración real.
- `SAPO_PREFS_POS=x,y`: abre la ventana en esa posición y sin quitarle el foco a lo que estés usando.
- `SAPO_PREFS_TAB=sapo|cerebro|voz|inicio|acerca`: abre directo en esa pestaña.
- `GEMINI_API_KEY`: si está definida, el botón Probar la usa cuando no hay una key guardada.

## Empaquetar

```bash
uv run python build.py
```

Genera el icono con Pillow y crea `dist/SapoPreferencias/SapoPreferencias.exe` con PyInstaller, en modo carpeta y sin consola. Incluye `pc/skins.json` y `assets/skins/*.svg`.
