# 01 — Mascota de escritorio (sapito kawaii) para Windows 11

> Objetivo: un sapito siempre encima de todo que salte por la pantalla, estorbe, arrastre ventanas, iconos y el mouse, y esté animado con esqueleto (rig).
> Restricción: todo 100 % gratis (open source o licencia gratuita).
> Fecha de la investigación: 2026-10-25. Las estrellas y fechas de GitHub salen de `api.github.com/repos/<repo>` consultada ese día.
> Hardware: Win11, RTX 5060 Ti 8 GB, i7-12700, 32 GB RAM.

---

## 1. Proyectos open source que ya existen

| Proyecto | Licencia | Stack | ⭐ | Actividad | ¿Se puede forkear? |
|---|---|---|---|---|---|
| **VPet-Simulator** (LorisYounger/VPet) | Apache-2.0 | C# / WPF; se puede meter en cualquier app WPF (NuGet `VPet-Simulator.Core`) | 7 030 | push 2026-10-24 | **Sí.** Gratis en Steam. Tiene sistema de mods/plugins. [repo](https://github.com/LorisYounger/VPet) · [Steam](https://store.steampowered.com/app/1920960/VPetSimulator/) |
| **BongoCat** (ayangweb/BongoCat) | Apache-2.0 (se cambió la licencia en el PR #1053) | Rust/Tauri, modelo Live2D que sigue al mouse y al teclado | 24 169 | push 2026-10-25 | **Sí.** El código sí; el SDK de Live2D Cubism tiene licencia propia. [repo](https://github.com/ayangweb/BongoCat) |
| **WindowPet** (SeakMengs/WindowPet) | MIT | TypeScript + Tauri (sprites) | 671 | último push 2025-04-11 | **Sí.** Es la referencia más cercana a un pet hecho con Tauri. [repo](https://github.com/SeakMengs/WindowPet) |
| **eSheep / desktopPet** (Adrianotiger/desktopPet) | MIT | C# (WinForms), animaciones definidas en XML | 1 164 | push 2026-10-23 | **Sí.** Camina sobre las ventanas, que es el comportamiento que buscamos. [repo](https://github.com/Adrianotiger/desktopPet) |
| **Shimeji-ee** (Kilkakon) | BSD-3 "New BSD", con un texto que escribió el propio Kilkakon; el Shimeji original de Yuki Yamada es zlib | Java, solo Windows | — (no está en GitHub; el código se baja como zip) | — | **Sí.** [kilkakon.com/shimeji](https://kilkakon.com/shimeji/) · fork activo [DalekCraft2/Shimeji-Desktop](https://github.com/DalekCraft2/Shimeji-Desktop) (55 ⭐, Java). Nota de licencia en [VShimeji](https://github.com/Valkryst/VShimeji) |
| **Desktop Goose** (samperson) | **Código cerrado**. Se descarga gratis en itch.io y tiene una API oficial de mods | C# WinForms + GDI+ (según comentarios de usuarios que lo descompilaron) | — | — | **No.** El repo [arkangel-dev/desktop-goose-source](https://github.com/arkangel-dev/desktop-goose-source) es una descompilación sin licencia, así que no hay que forkearlo. Sirve como inspiración de comportamiento (traer ventanas o notas, robar el cursor). [itch](https://samperson.itch.io/desktop-goose) · [comentarios](https://samperson.itch.io/desktop-goose/comments?before=150) |
| Godot Multiple-Windows tutorial (geegaz) | MIT | Godot 4 (GDScript): personaje que sale de la ventana | 522 | 2024-09 | Sí. Sirve como plantilla. [repo](https://github.com/geegaz/Multiple-Windows-tutorial) · fork orientado a pet: [phanstudio/Desktop-Pet](https://github.com/phanstudio/Desktop-Pet/) |
| godot-native-click-through | MIT | GDExtension C++ para click-through en Windows | 3 | 2026-07 | Sí. [repo](https://github.com/KhangQuachUnique/godot-native-click-through) |

**Conclusión 1:** para robar el comportamiento de caminar sobre ventanas lo mejor es leer **eSheep** (C#). Para la arquitectura de un pet con mods, **VPet**. Para Tauri, **WindowPet** y **BongoCat**. Ninguno trae un rig esquelético 2D genérico: VPet usa animaciones por frames y BongoCat usa Live2D.

---

## 2. Ventana transparente, siempre encima y click-through selectivo

| Stack | Transparente per-pixel | Siempre encima | Click-through | RAM en reposo | Notas |
|---|---|---|---|---|---|
| **Godot 4** (MIT) | `display/window/per_pixel_transparency/allowed` + `transparent_bg` + `borderless` ([Window docs](https://docs.godotengine.org/en/stable/classes/class_window.html), [foro](https://forum.godotengine.org/t/how-can-i-make-a-transparent-app-on-windows/110395)) | propiedad `always_on_top` | `mouse_passthrough_polygon`: "polygonal region of the window which accepts mouse events. Mouse events outside the region will be passed through" ([docs](https://docs.godotengine.org/en/stable/classes/class_window.html)) | No encontré un benchmark fiable. **Hay que medirlo.** | En Windows, `window_set_mouse_passthrough` usa `SetWindowRgn`, que **recorta input y también render** a la región ([Kalgator demo](https://github.com/Kalgator/Godot-4-Mouse-Passthrough)). Por eso conviene una ventana pequeña que se mueva con el sapo, o alternar `WS_EX_TRANSPARENT` por P/Invoke. Trae motor de física, Skeleton2D, AnimationPlayer y C# (.NET). |
| **Tauri v2** (Apache-2.0/MIT, 112k ⭐) | `transparent: true`, `decorations: false` | `setAlwaysOnTop()` | `setIgnoreCursorEvents(ignore)` es **todo o nada**: no hay región; el hit-test se hace a mano con un polling del cursor ([window.ts](https://github.com/tauri-apps/tauri/blob/dev/packages/api/src/window.ts), [issue #10564](https://github.com/tauri-apps/tauri/issues/10564)) | 142 MB privados en Win11 (incluye WebView2) ([dawloom](https://dawloom.com/blog/tauri-vs-electron-vs-wpf-benchmark/)) | También trae `setCursorPosition`, `setSkipTaskbar` y `setPosition` (mismo window.ts). Instalador de ~1 MB. |
| **Electron** (MIT, 123k ⭐) | `transparent: true` | `setAlwaysOnTop` | `win.setIgnoreMouseEvents(true, { forward: true })`: deja pasar los clics pero sigue recibiendo `mousemove`, lo que permite click-through selectivo ([docs](https://www.electronjs.org/docs/latest/tutorial/custom-window-interactions)). Tiene bugs abiertos con `forward` ([#33281](https://github.com/electron/electron/issues/33281)) | 149 MB ([dawloom](https://dawloom.com/blog/tauri-vs-electron-vs-wpf-benchmark/)). Otra medición con 6 ventanas: 409 MB frente a 172 MB de Tauri ([Hopp](https://www.gethopp.app/blog/tauri-vs-electron)) | Instalador de ~106 MB. Es el que mejor resuelve el click-through selectivo de forma nativa. |
| **WPF / C#** (MIT) | `AllowsTransparency` | `Topmost` | `WS_EX_TRANSPARENT` por P/Invoke | 74 MB ([dawloom](https://dawloom.com/blog/tauri-vs-electron-vs-wpf-benchmark/)) | Es lo que usan VPet y eSheep. No trae motor de rig. |
| **Unity** | Posible con hacks de Win32 | — | — | — | Unity Personal es gratis solo con menos de 200 000 USD de ingresos ([unity.com](https://unity.com/products/unity-personal)). El motor no es open source, así que **no cumple la restricción**. |
| **Python + PySide6** (LGPL) | `WA_TranslucentBackground` ([QWidget docs](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html)) | `WindowStaysOnTopHint` | `WindowTransparentForInput` o `WS_EX_TRANSPARENT` | sin medir | Sirve para prototipar rápido. No trae rig ni física: habría que añadir pymunk o similar. |

---

## 3. Controlar el mouse, las ventanas ajenas y el teclado en Windows

### API Win32 (base de todo)
- **Mover el cursor:** `SetCursorPos`. Microsoft lo advierte: "The cursor is a shared resource. A window should move the cursor only when the cursor is in the window's client area" ([docs](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setcursorpos)). Funciona fuera de esa zona, pero es una advertencia de buenas prácticas, y conviene hacerlo por el modo "travieso" con un toggle.
- **Simular clics y teclas:** `SendInput`. Está sujeto a **UIPI**: "permitted to inject input only into applications that are at an equal or lesser integrity level", y falla **en silencio** ([docs](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)). Consecuencia: no puede tocar ventanas abiertas como Administrador salvo que el sapo también corra elevado (no recomendado).
- **Arrastrar ventanas ajenas:** `GetWindowRect` y luego `SetWindowPos(hwnd, …, SWP_NOZORDER|SWP_NOACTIVATE)` en un bucle, para que la ventana siga al sapo.
- **Detectar ventanas y sus bordes, para caminar encima:** `EnumWindows` + `IsWindowVisible` + `IsIconic`. Para el borde visible real de Win11 (sin la sombra invisible) se usa `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)`. Para descartar ventanas UWP ocultas, `DWMWA_CLOAKED` ([enum DWMWINDOWATTRIBUTE](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute)). El borde superior de cada ventana es una "plataforma".
- **Taskbar como suelo:** `SHAppBarMessage(ABM_GETTASKBARPOS)` da el rectángulo de la barra del sistema ([docs](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shappbarmessage)). También sirve `SystemParametersInfo(SPI_GETWORKAREA)`.
- **Mover iconos del escritorio:** son items de un `SysListView32` dentro de `Progman`/`WorkerW`. Se mueven con `SendMessage(hList, LVM_SETITEMPOSITION, idx, MAKELPARAM(x,y))` ([SO C](https://stackoverflow.com/questions/76020228/how-to-move-desktop-icons-using-winapi-on-c/76043631), [SO Python](https://stackoverflow.com/questions/71905594/how-to-move-desktop-icons-with-python)). Hay que identificar los iconos por nombre y no por índice, porque los índices se reordenan ([Restore-DesktopIcons](https://github.com/gronaldo44/Restore-DesktopIcons)). Riesgo: desordenar el escritorio del usuario, así que hay que **guardar las posiciones y restaurarlas al salir**.

### Librerías (todas gratis)
| Librería | Licencia / ⭐ | Lenguaje | Comentario |
|---|---|---|---|
| robotjs | MIT / 12.8k | Node (addon C) | Mouse, teclado y pantalla. Es un addon nativo, así que hay que recompilarlo por cada versión de Electron/Node. [repo](https://github.com/octalmage/robotjs) |
| nut.js | código en GitHub / 2.8k | Node | **Ojo:** los paquetes precompilados de npm ahora son de pago (Core cuesta 20 USD/mes, [pricing](https://nutjs.dev/pricing)). El README dice que "is still free to use, you'll just have to build it from sources" ([repo](https://github.com/nut-tree/nut.js/)). Solo se puede usar si lo compilamos nosotros. |
| pyautogui | BSD-3 / 12.7k | Python | Mouse y teclado sencillos. [repo](https://github.com/asweigart/pyautogui) |
| pywinauto | BSD-3 / 6.2k | Python | Automatización de ventanas y controles. [repo](https://github.com/pywinauto/pywinauto) |
| mouse (boppreh) | MIT / 959 | Python | Hooks globales del mouse. [repo](https://github.com/boppreh/mouse) |
| AutoHotkey v2 | GPL-2.0 / 13.4k | AHK | Ideal para prototipar comportamientos (WinMove, MouseMove). La GPL importa si se distribuye junto con el sapo. [repo](https://github.com/AutoHotkey/AutoHotkey) |
| **P/Invoke directo (C#)** | — | C# en Godot .NET o WPF | Sin dependencias: `[DllImport("user32.dll")]` para todo lo anterior. **Es la opción recomendada.** |

---

## 4. Animación con esqueleto, gratis

| Herramienta | ¿Gratis? | Estado / notas |
|---|---|---|
| **Godot Skeleton2D + Bone2D + Polygon2D** | **Sí (MIT)** | Rig con deformación de malla: se asignan pesos por hueso en el editor UV del Polygon2D ([tutorial 2D skeletons](https://docs.godotengine.org/en/stable/tutorials/animation/2d_skeletons.html), [Skeleton2D](https://docs.godotengine.org/en/stable/classes/class_skeleton2d.html)). El **IK 2D** (`SkeletonModificationStack2D`, CCDIK/FABRIK) existe pero está marcado como **"Experimental: may be changed or removed"** ([docs](https://docs.godotengine.org/en/stable/classes/class_skeletonmodificationstack2d.html)). |
| **Rive** | **No para exportar.** | Desde el 2025-10-20 el editor sigue siendo gratis pero "Exports move to paid plans" (Cadet cuesta 9 USD/mes anual). Los runtimes siguen siendo MIT ([blog Rive](https://rive.app/blog/rive-s-new-9-mo-plan)). **Queda descartado** por la restricción. |
| **Spine** | **De pago (confirmado)** | Comprar Spine "enables saving projects and exporting". Essential cuesta 69–99 USD y Enterprise 2 499 USD ([purchase](https://esotericsoftware.com/spine-purchase), [ES](https://es.esotericsoftware.com/spine-purchase)). **Descartado.** |
| **DragonBones** | Gratis | "No longer under development" ([Lospec](https://lospec.com/software/dragonbones)). Descarga en [dragonbones.github.io](https://dragonbones.github.io/en/download.html). El runtime JS es MIT (857 ⭐, último push 2026-01). Funciona, pero está abandonado y no lo recomiendo para un proyecto nuevo. |
| **Live2D Cubism** | FREE limitado + PRO de pago | El FREE se puede usar comercialmente solo por "General Users and Small-Scale Enterprises (annual sales less than 10 million yen)" y tiene límites como **máx. 30 partes**; si los superas no puedes guardar ([comparación](https://www.live2d.com/en/cubism/comparison/)). PRO tiene 42 días de prueba ([about](https://www.live2d.com/en/cubism/about/)). Para un sapo sencillo cabe en FREE, pero el editor no es open source. |
| **Inochi2D** | **Sí (BSD-2)** | Es la alternativa libre a Live2D: "Inochi2D is free, BSD 2-clause licensed software" ([FAQ](https://docs.inochi2d.com/en/latest/inochi2d/faq.html)). inochi2d tiene 1.8k ⭐ y inochi-creator 1.25k ⭐ ([repo](https://github.com/Inochi2D/inochi-creator)). Encaja más con un estilo puppet o VTuber que con saltos y física. |
| iki (zeikar/iki) | MIT | Motor puppet 2D web con auto-rigger por IA. Es muy nuevo (23 ⭐) ([repo](https://github.com/zeikar/iki)). Experimental. |

**Física y "jugo" de la animación:**
- **Ragdoll:** en Godot, un `RigidBody2D` por hueso unido con `PinJoint2D`. Se activa al lanzarlo o arrastrarlo y luego se mezcla de vuelta a la animación.
- **Squash & stretch:** basta con interpolar `scale` (por ejemplo x 1.3 / y 0.7 al aterrizar) con `Tween` o `AnimationPlayer`, más la gravedad del `CharacterBody2D`.
- **Ojos y cachetes con "jiggle":** con resortes amortiguados en GDScript (spring de segundo orden). No hacen falta librerías.

**Para dibujar el sapo (todo gratis):**
- **Krita** (GPL): ilustración por capas. Separa las partes (cuerpo, ojos, patas, boca) en PNG para montarlas en Polygon2D.
- **Inkscape** (GPL): vector, útil si el estilo kawaii es plano.
- **Pixelorama** (MIT, 10.8k ⭐, hecho en Godot) ([repo](https://github.com/Orama-Interactive/Pixelorama)) o **LibreSprite** (GPL-2.0, 8.6k ⭐) ([repo](https://github.com/LibreSprite/LibreSprite)), si se va a pixel art.
- **Aseprite** es source-available, no open source (la descarga oficial es de pago) ([Wikipedia](https://en.wikipedia.org/wiki/Aseprite), [FAQ](https://www.aseprite.com/faq/)). Que se pueda usar gratis compilándolo tú mismo lo dicen terceros ([libhunt](https://www.libhunt.com/compare-aseprite-vs-LibreSprite)); **no lo verifiqué en el EULA**. Mejor usar Pixelorama o LibreSprite.

---

## 5. Recomendación de stack

**Godot 4.x (.NET/C#) + P/Invoke a user32/dwmapi + rig Skeleton2D/Polygon2D + arte en Krita.**

Justificación:
1. **Todo es MIT/GPL y gratis.** Godot no tiene royalties. Rive y Spine quedan fuera porque exportar cuesta.
2. **Rig, física y animación en una sola herramienta:** Skeleton2D, deformación de malla, AnimationTree, RigidBody2D para ragdoll y Tween para squash & stretch. Con Tauri o Electron habría que juntar PixiJS + un runtime de rig (DragonBones, abandonado) + física aparte.
3. **Ventana transparente y siempre encima nativas** (`transparent_bg`, `always_on_top`, `mouse_passthrough_polygon`).
4. **C# permite P/Invoke directo** a SetCursorPos, SendInput, SetWindowPos, EnumWindows, DwmGetWindowAttribute, SHAppBarMessage y LVM_SETITEMPOSITION, sin addons nativos que recompilar como robotjs o nut.js.
5. **Rendimiento:** el render es por GPU (la RTX 5060 Ti sobra). El consumo de RAM **está pendiente de medir**; no encontré un benchmark fiable de Godot para este caso.

**Arquitectura propuesta**
- La ventana es **pequeña, del tamaño del sapo más un margen**, y se mueve con `DisplayServer.window_set_position`. Así se evita el problema de `SetWindowRgn`, que recorta el render en una ventana fullscreen. El `mouse_passthrough_polygon` se ajusta a la silueta del sapo.
- Un `WorldScanner` (C#) se ejecuta cada ~200 ms: enumera las ventanas visibles, toma sus bordes DWM y la taskbar, y construye las "plataformas" donde caminar y saltar.
- Un `MischiefController` con una máquina de estados: idle → caminar → saltar a ventana → agarrar la ventana (`SetWindowPos`) → robar el mouse (`SetCursorPos`, con un tirón suave) → empujar iconos (guardando y restaurando posiciones).
- **Seguridad y UX:** una tecla global de pánico, un modo "tranquilo", no tocar ventanas elevadas (UIPI de todos modos lo impide) y restaurar los iconos al salir.

**Plan B (web):** Tauri v2 + PixiJS (MIT, 48k ⭐) con sprites o rig propio, más un sidecar en Rust para Win32. Es más ligero de instalar, pero el click-through es todo o nada ([issue #10564](https://github.com/tauri-apps/tauri/issues/10564)) y no hay un rig gratis maduro para web.
