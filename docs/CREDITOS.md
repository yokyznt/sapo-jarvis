# Créditos y licencias

Sapo es MIT. Usa o distribuye estos componentes:

| Componente | Uso | Licencia |
|---|---|---|
| [Godot Engine](https://godotengine.org) 4.7 | Motor del sapo (`Sapo.exe`) | MIT |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Voz a texto, texto a voz y VAD | Apache-2.0 |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (multi-lang v1.0) | Voz local | Apache-2.0 |
| NVIDIA NeMo FastConformer CTC español (sherpa-onnx int8) | Reconocimiento de voz | CC-BY-4.0: © NVIDIA, modelo convertido por k2-fsa |
| [Silero VAD](https://github.com/snakers4/silero-vad) | Detección de voz | MIT |
| [FFmpeg](https://ffmpeg.org) | Clips nativos (programa externo, no se distribuye) | LGPL/GPL según el build |
| [OBS Studio](https://obsproject.com) | Clips en pantalla completa exclusiva (programa externo) | GPL-2.0 |
| [Ollama](https://ollama.com) | IA local (programa externo) | MIT |
| [pywebview](https://pywebview.flowrl.com) | Ventana de Preferencias | BSD-3-Clause |
| [websockets](https://github.com/python-websockets/websockets) | Comunicación sapo ↔ cerebro | BSD-3-Clause |
| [httpx](https://www.python-httpx.org) | API de Gemini | BSD-3-Clause |
| [soundcard](https://github.com/bastibe/SoundCard) | Audio del sistema en clips | BSD-3-Clause |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) / PortAudio | Micrófono y bocina | MIT |
| [NumPy](https://numpy.org) | Audio | BSD-3-Clause |
| [Pillow](https://python-pillow.org) | Capturas e imágenes | MIT-CMU |
| [pypdf](https://github.com/py-pdf/pypdf) | Leer PDFs soltados | BSD-3-Clause |
| [PyInstaller](https://pyinstaller.org) | Empaquetado | GPL-2.0 con excepción de bootloader (permite distribuir) |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Instalador | Licencia Inno Setup (gratis) |

Gemini es un servicio de Google con sus propios [términos](https://ai.google.dev/gemini-api/terms). Los croacs son sintetizados por el propio sapo; no hay audios de terceros.
