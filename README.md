# Sapo 🐸

Mascota-asistente de escritorio gratis y de código abierto: un sapito que vive encima de tu pantalla, brinca sobre tus ventanas, te roba el cursor con la lengua cuando lo ignoras y, pronto, te escucha ("oye sapo"), controla tu PC y tu celular y contesta WhatsApp por ti cuando estás ocupado. Todo local, sin telemetría.

<img src="assets/skins/clasico.svg" width="120" alt="Clásico"> <img src="assets/skins/hojita.svg" width="120" alt="Hojita"> <img src="assets/skins/lavanda.svg" width="120" alt="Lavanda"> <img src="assets/skins/noche.svg" width="120" alt="Noche"> <img src="assets/skins/dorado.svg" width="120" alt="Dorado"> <img src="assets/skins/gotita.svg" width="120" alt="Gotita">

## Estado

Fase 1 en progreso: el sapo en Windows.

- Ventana transparente encima de todo; solo el sapo recibe clics.
- Cuerpo de gelatina que se aplasta y rebota.
- Brinca sobre los bordes de las ventanas y las sigue si las mueves.
- Lo agarras y lo avientas; un clic lo acaricia.
- Si lo ignoras se aburre: te jala el cursor y las ventanas con la lengua y pisotea ventanas.
- Con un juego o video en pantalla completa se duerme y no toca nada (si es en su monitor, se esconde).

Fase 2 (cerebro): IA local con Ollama (`qwen3.5:4b` en GPU, `qwen3.5:2b` en CPU durante juegos, Groq opcional con tu key), personalidad sarcástica, memoria SQLite, vida propia y burbujas de diálogo. Voz con "oye sapo" y respuestas habladas, y control de la PC (apps, web, volumen, música, recordatorios, ventanas, "qué hay en mi pantalla", apagar con confirmación). Ver [brain/README.md](brain/README.md).

Ver [docs/PLAN.md](docs/PLAN.md) y [docs/DECISIONES.md](docs/DECISIONES.md).

## Instalar

Descarga `Sapo-Setup-<versión>.exe` de Releases y ábrelo (no pide administrador). Crea Sapo y Sapo Preferencias en el menú Inicio, icono en la bandeja y, si quieres, arranque con Windows. Los modelos de voz (≈510 MB) se bajan aparte la primera vez.

Construir: `python scripts/build_release.py` (necesita Godot 4.7 mono con export templates, uv e Inno Setup 6).

## Accesos en el menú Inicio

`powershell -ExecutionPolicy Bypass -File scripts/accesos.ps1` crea "Sapo" (arranca cerebro, voz y sapo sin ventanas) y "Sapo Preferencias" en el buscador de Windows. Sin admin.

## Preferencias

`settings/dist/SapoPreferencias/SapoPreferencias.exe` (compilar con `cd settings && uv run python build.py`): diseño, tamaño, energía, nenúfar, cerebro (Gemini o local, key cifrada), voz e inicio con Windows. Los cambios se aplican al sapo en vivo.

## Atajos

| Tecla | Acción |
|---|---|
| Ctrl+Alt+S | Calmar / despertar |
| Ctrl+Alt+Q | Cerrar |
| Clic derecho en el sapo | Menú: fijar en nenúfar, dormir, diseño, energía, tamaño, salir |

## Correr desde el código

Requisitos: Windows 10/11, [Godot 4.7 .NET](https://godotengine.org/download/windows/), .NET SDK 8+.

```
cd pc
dotnet build
Godot_v4.7.2-stable_mono_win64.exe --path . -- --monitor=0
```

Opciones: `--monitor=N`, `--point=x,y` (monitor que contiene ese punto), `--boredom=0..1`.

## Licencia

MIT.
