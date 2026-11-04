# Dataset card · Riesgo sectorial SIGRIF

## Resumen

| Campo | Valor |
|---|---|
| Nombre | `sigrif_risk_synthetic` |
| Archivo | `data/training/sigrif_risk_synthetic.csv` |
| Registros | 3000 |
| Variables de entrada | 6 |
| Variable objetivo | `risk_level` con clases `Bajo`, `Medio`, `Alto` |
| Naturaleza | Sintética, con fines académicos |
| Semilla | 42 |
| Hash SHA-256 | `48da94a8e80d7fb0aaeced3f1b60f9bafa9f042e06b33e66b8969cb6662a7fdf` |
| Fecha de generación | 2026-11-04 |

## Variables

| Variable | Tipo | Rango | Unidad | Papel |
|---|---|---|---|---|
| `temperature` | continua | 5–40 | °C | Condición meteorológica. |
| `humidity` | continua | 10–90 | % | Humedad relativa; valores bajos aumentan el riesgo. |
| `wind_speed` | continua | 0–80 | km/h | Favorece la propagación. |
| `vegetation` | continua | 0–1 | índice | Combustible disponible; es una palanca de gestión. |
| `historical_fires` | entera | 0–15 | eventos | Recurrencia histórica del sector. |
| `slope` | continua | 0–45 | grados | Pendiente; dificulta el acceso y la respuesta. |

Las seis variables se conservaron porque el equipo decidió mantener `slope`
junto con `historical_fires`. La pendiente aporta contexto territorial y las
bases del caso la consideran una variable opcional; su inclusión se documenta
como decisión del equipo, no como un requisito oficial.

## Construcción de la etiqueta

Cada fila recibe un `rule_score` ponderado:

```text
0.30 × temperatura_normalizada
+ 0.20 × (1 − humedad_normalizada)
+ 0.15 × viento_normalizado
+ 0.15 × vegetación
+ 0.10 × incendios_históricos_normalizados
+ 0.10 × pendiente_normalizada
```

Luego se aplican los umbrales `> 0.62` para `Alto`, `> 0.42` para `Medio` y el
resto para `Bajo`. La regla es una construcción académica del equipo; no es un
estándar oficial de CONAF ni de SENAPRED.

## Distribución y calidad

| Clase | Registros aproximados | Observación |
|---|---|---|
| Bajo | 580 | Casos de menor exposición relativa. |
| Medio | 1821 | Clase mayoritaria de la simulación. |
| Alto | 599 | Casos de mayor exposición relativa. |

No hay valores nulos. Los rangos se mantienen dentro de los límites definidos en
`src/sigrif/model_spec.py`. El dataset no contiene identificadores personales ni
datos sensibles.

## Fuentes y trazabilidad

El dataset es una simulación. Para fijar rangos y unidades se tomaron como
referencia los datos meteorológicos y territoriales disponibles en el material
del curso: estaciones de la Red EMA de la DMC, catastro de incendios de CONAF y
las bases del concurso SIGRIF. No se usaron esos registros para etiquetar los
sectores, porque no existe una etiqueta oficial de riesgo por sector que cubra
todas las zonas del prototipo.

| Fuente | Uso en este dataset | Enlace |
|---|---|---|
| DMC · Red EMA | Rangos y unidades de temperatura, humedad y viento. | https://climatologia.meteochile.gob.cl/ |
| CONAF · incendios históricos | Referencia conceptual para la variable de recurrencia. | https://www.conaf.cl/ |
| Bases del caso SIGRIF | Variables principales y opcionales. | Documento del curso |

## Reproducibilidad

```bash
make train
```

La generación usa `numpy.random.default_rng(42)`. El hash del CSV se guarda en
`ml/model_metadata.json` y permite verificar que el artefacto corresponde a una
ejecución concreta.

## Límites

- La etiqueta depende de una regla, por lo que el modelo aprende esa regla y no
  el comportamiento real del territorio.
- La distribución sintética no representa la frecuencia real de incendios.
- La variable `historical_fires` es un conteo simulado; cuando se conecte una
  fuente real habrá que definir la ventana temporal y la unidad espacial.
- El dataset no reemplaza una validación con CONAF, DMC o SENAPRED.
