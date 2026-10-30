# 02 · Arrastre entre monitores

Etiqueta: `s02-monitores` · Archivos: pc/src/Frog.cs, pc/src/Desktop.cs

## Tareas
- [x] Detectar salida del área de trabajo al arrastrar o saltar
- [x] Mover la ventana al monitor destino y trasladar coordenadas
- [ ] Soportar tamaños y DPI distintos
- [x] Salto autónomo al otro monitor cuando comparten borde

## Criterios de aceptación
- [ ] Arrastrar del principal al de arriba y de regreso
- [ ] El sapo no se corta ni se teletransporta
- [ ] Plataformas del monitor nuevo se recalculan

## Bugs y arreglos

| Fecha | Descripción | Estado | Commit/Issue |
|---|---|---|---|
| 2026-10-30 | Al arrastrar rápido se cortaban pedazos del sapo (la región de la ventana iba un cuadro atrás) | Arreglado: región con margen según la velocidad y la sombra incluida; 0 cortes en 30 cuadros de arrastre rápido (antes 2 de 9) | etapa-3 |
