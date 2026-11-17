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
| 2026-10-30 | En el monitor de arriba caía sobre un piso invisible a ~260 px: el muelle transparente de Seelen UI contaba como ventana | Arreglado: se ignoran docks/overlays (topmost+noactivate y lista de procesos); 3 lanzamientos caen al piso real | etapa-4 |
| 2026-10-30 | Aventado hacia arriba desde el monitor principal caía en el piso del monitor de arriba (mitad del escritorio) | Arreglado: cae de vuelta al piso del monitor desde donde lo aventaste; 2 lanzamientos desde el principal y 12 en el de arriba correctos | etapa-6 |
| 2026-10-30 | 'Onda de aire' hacia donde va el sapo al aventarlo/arrastrarlo | Arreglado: la región de la ventana ya no crece en círculo grande; solo se adelanta el contorno 2 cuadros y el fondo de la clase de ventana es nulo (sin pintado blanco) | etapa-6 |
| 2026-10-30 | Mancha/silueta transparente detrás del sapo al arrastrarlo o aventarlo (la región de la ventana cambiaba cada cuadro y Windows dejaba pedazos viejos) | Arreglado: mientras está agarrado o en el aire la región no cambia; se recalcula al aterrizar | etapa-6 |
| 2026-10-30 | El usuario pidió que al aventarlo hacia el monitor de arriba se quede arriba | Hecho: cae en el piso del monitor donde termina | etapa-6 |
| 2026-10-31 | En el piso, clic derecho: el menú se amontonaba y un clic activaba varias cosas (las opciones se apilaban al recortarse contra el borde y el dock transparente de Seelen quedaba encima del sapo, así que el clic también le llegaba al escritorio/dock) | Arreglado: columnas que se acomodan completas sin encimarse y suben arriba del sapo cerca del piso; el sapo se vuelve a poner encima si otra ventana lo tapa; probado 5/5 (un clic = una opción) en tamaños chico y grande | etapa-7 |
