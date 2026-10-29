# Sapo v2: plan

Base: PR #1 (sapo Godot + cerebro + voz local + 18 herramientas). Reglas: código sin comentarios, sin admin, público MIT, nada de llaves en el repo.

Skills por sección: `godot-gdscript-patterns`, `feel` / `fluid-design` (física y resortes), `12-principles-of-animation`, `animated-sprites` (skins), `gemini-api-dev`, `gemini-live-api-dev`, `gemini-tts`, `generating-sounds-with-ai` (croacs), `windows-desktop-apps`, `tdd`, `code-review`, `dispatching-parallel-agents`.

## 1. Diseño y skins
- Cuerpo: blob único tipo Grok/Coucou, sin extremidades: silueta redonda con dos jorobas de ojos fundidas, contorno grueso uniforme, ojos negros con un brillo, chapitas, sonrisa de una curva.
- Animación más lenta y suave: resortes con menos rigidez, rebote corto, respiración visible, parpadeos espaciados.
- Skins como datos (`pc/skins/*.json`: colores, contorno, forma de ojos, accesorio opcional dibujado en la cabeza): Clásico, Menta, Rosa, Noche, Dorado, Axolote-rana, Hojita (con hoja en la cabeza), Gotita. Selector en ajustes; vista previa en vivo.
- `assets/skins/*.svg` generados del mismo JSON para el README.

## 2. Dos monitores
- Una ventana por monitor no; una sola ventana que salta de monitor: al arrastrar o saltar más allá del borde, la ventana se mueve al área de trabajo del monitor destino y las coordenadas se trasladan. Soporta tamaños y DPI distintos.
- El sapo puede saltar solo al otro monitor si las orillas se tocan (tu monitor de arriba comparte borde con el principal).

## 3. Nenúfar
- Clic derecho en el sapo → menú radial: Fijar aquí / Soltar / Dormir / Ajustes / Clipear / Salir.
- "Fijar aquí" pone un nenúfar debajo; el sapo se queda ahí (no salta ni roba cursor), solo respira, parpadea, mira y habla. Arrastrar el nenúfar lo mueve. Posición guardada por monitor.

## 4. Menos hiperactivo
- Nivel de energía en ajustes (Zen / Normal / Travieso). Default Normal: salto cada 20–60 s, robar cursor solo en Travieso.
- Habla: máximo 1 comentario espontáneo cada 8–15 min (ajustable), nunca dos seguidos sin que respondas, silencio total en reuniones/llamadas/pantalla compartida y en modo juego.

## 5. Atención al primer plano
- Cada 3 s lee ventana activa (proceso + título). Solo comenta cuando cambia de actividad y lleva >2 min en ella.
- Contexto barato primero (título/proceso: "VS Code – Frog.cs", "Spotify – canción"); captura con visión solo si el contexto no alcanza y como máximo cada 10 min, a resolución reducida.
- Lista negra por defecto: bancos, gestores de contraseñas, WhatsApp, correo, ventanas privadas del navegador, Hermes. Configurable. Nunca captura en modo juego.
- Memoria de actividad del día ("llevas 3 h en Roblox") para comentarios con sentido.

## 6. Cerebro con Gemini
- Proveedor intercambiable: Gemini (default para ti) → Ollama local de respaldo (sin internet, sin key o si se agota el cupo).
- Gemini Flash del plan gratis para chat, herramientas y visión; Flash-Lite para comentarios espontáneos (más cupo). IDs exactos con `models.list` al implementar.
- Key de Gemini: la pones en Ajustes; se guarda cifrada con DPAPI de Windows en `%APPDATA%\Sapo`, nunca en el repo. Cada usuario público usa su propia key.
- Gemini quita el problema de la GPU en juegos (corre en la nube), así que en modo juego también usa Gemini.
- Frases: prompt nuevo con personaje fijo (sapo sarcástico pero útil), 15 ejemplos buenos y 15 prohibidos, reglas de coherencia (responder a lo que pasa, nada genérico), filtro anti-repetición contra las últimas 50 frases, longitud 4–18 palabras.
- Memoria: resumen diario automático + hechos importantes; embebidos con `text-embedding` de Gemini o sqlite-vec local.

## 7. Voz con Gemini
- Palabra clave "oye sapo" sigue local (privado, gratis, 0 latencia).
- Tras la palabra clave: sesión Gemini Live (audio a audio, plan gratis) para conversación natural con interrupciones; se cierra tras 20 s de silencio.
- Frases espontáneas: Gemini TTS Flash-Lite con voz elegible y estilo ("voz chiquita, burlona"); caché en disco de frases repetidas.
- Respaldo automático a STT NeMo + Kokoro si no hay red/key/cupo.
- Boca sincronizada con el volumen del audio (amplitud → apertura de boca).

## 8. Sonidos de rana
- Croacs procedurales generados en código (sin licencias de terceros): 8 variantes (croac corto, doble, gruñón, feliz, sueño, sorpresa, aterrizaje, "plop" al caer en el nenúfar).
- Casuales: 1 cada 3–10 min, al aterrizar fuerte, al acariciar, al despertar. Volumen y frecuencia en ajustes; silencio en reuniones/juego.

## 9. Interacciones con Windows
- Ventana maximizada bajo él → se cae; minimizada → salta asustado; ventana movida → se tambalea.
- Se sienta en la barra de tareas y en el reloj; a cada hora en punto croa.
- Notificaciones nuevas: voltea a la esquina.
- Batería baja, sin internet, volumen en 0, papelera llena, portapapeles nuevo, captura de pantalla tomada: reacción corta (gesto, croac o frase rara vez).
- Arrastrar un archivo sobre el sapo: "¿qué es esto?" → lo resume (texto/imagen/PDF) con Gemini.
- Doble clic: abre chat de texto en burbuja.

## 10. Clips ("sapo clipea eso")
- Nativo (default): FFmpeg con `ddagrab` + `h264_nvenc` grabando en búfer circular de segmentos de 2 s en `%LOCALAPPDATA%\Sapo\buffer` (últimos 2 min), audio del sistema por WASAPI loopback (`soundcard`) mezclado al exportar. "Clipea eso" une los últimos 30 s (configurable) → `Videos\Sapo Clips\fecha.mp4` y avisa con croac + burbuja.
- No inyecta teclas ni toca el juego (seguro con anti-cheat). NVENC casi no afecta FPS.
- Alternativas en ajustes: Medal (envía su atajo) o Xbox Game Bar (Win+Alt+G). Ambas mandan una tecla simulada: opción no recomendada con juegos con anti-cheat.
- Funciona por voz aunque el sapo esté dormido en modo juego.

## 11. Ajustes y bandeja
- Icono en la bandeja (Godot StatusIndicator) con: Ajustes, Calmar, Fijar/Soltar, Clipear, Salir.
- Ventana de ajustes (Godot UI) con pestañas: Sapo (skin, tamaño, monitor, energía), Voz (voz, tono, palabra clave, micrófono), Cerebro (proveedor, key, modelo, frecuencia de comentarios, lista negra), Sonidos, Clips (duración, calidad, carpeta, método), Inicio (arrancar con Windows).
- Un solo `config.json` en `%APPDATA%\Sapo` compartido por sapo, cerebro y voz; cambios en vivo por WebSocket.

## 12. Ejecutable y arranque con Windows
- `Sapo.exe` (export de Godot; plantillas oficiales gratis) que lanza el cerebro y la voz como procesos hijos ocultos y los reinicia si se caen.
- Cerebro + voz empaquetados con PyInstaller (onedir) → `sapo-core.exe`; modelos locales se bajan al primer uso.
- Instalador Inno Setup (gratis) por usuario, sin admin: `%LOCALAPPDATA%\Programs\Sapo`, acceso directo, desinstalador, autoinicio en `HKCU\...\Run` (interruptor en ajustes).
- GitHub Releases + winget después.

## 13. Pruebas
- pytest: proveedor Gemini falso, selector de proveedor/respaldo, anti-repetición, rate limit de comentarios, lista negra, búfer de clips (con video sintético), config.
- Godot: compilación sin advertencias + capturas recortadas x4 en tu monitor de arriba (skins, nenúfar, cambio de monitor, menú).
- Prueba real con Gemini: chat, herramienta, visión, TTS 2 s y Live 1 turno; clip real de 10 s del monitor de arriba.

## 14. Orden y subagentes
| Ola | Paralelo | Toca |
|---|---|---|
| A | A1 Sapo: diseño, skins, energía, monitores, nenúfar, menú, sonidos, interacciones Windows | `pc/` |
| A | A2 Cerebro: proveedor Gemini, frases, memoria, atención al primer plano | `brain/sapo/` excepto `voice/` y `clips/` |
| A | A3 Voz: Gemini Live + TTS + respaldo + boca sincronizada | `brain/sapo/voice/` |
| A | A4 Clips: búfer FFmpeg + exportar + comando | `brain/sapo/clips/` |
| B | Ajustes + bandeja + config compartida | `pc/` + `brain/sapo/config.py` |
| C | Empaquetado, instalador, autoinicio, README | `packaging/` |
| D | Revisión (`code-review`), prueba integral, PR, resumen por WhatsApp | todo |

Cada subagente: sin git, sin comentarios, archivos propios; el orquestador integra, prueba y hace commit.

## 15. Lo que necesito de ti
- Key gratis de Gemini (aistudio.google.com → Get API key) pegada en Ajustes, no en el chat.
- Confirmar si con el plan gratis aceptas que Google use tus conversaciones y capturas para mejorar sus productos.
- Decir si tu Fortnite va en pantalla completa exclusiva (el clip nativo solo graba borderless/ventana).

## 16. Límites conocidos
- Plan gratis de Gemini: Google usa los datos para entrenar, pide 18+, cupos diarios bajos y modelos Pro no disponibles; sin cupo cae a local.
- Pantalla completa exclusiva: Desktop Duplication no la captura; usar borderless o el método Game Bar/Medal.
- Exe sin firmar: aviso de SmartScreen la primera vez (firmar cuesta).
- Ventanas abiertas como administrador: el sapo no puede moverlas ni pararse encima de forma interactiva.
- Medal no tiene API pública: solo se le puede mandar su atajo.
