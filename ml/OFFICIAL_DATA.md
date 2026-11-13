# Datos oficiales de las zonas SIGRIF

Este documento describe el enriquecimiento de las 560 zonas operativas de la
Región de Valparaíso con datos de CONAF, incendios y DEM. Reemplaza los priors
académicos de `vegetation`, `historical_fires` y `slope` solo cuando la fuente
cubre la zona. La capa resultante es:

```
src/sigrif/data/cerros_sectores_valparaiso_region_oficial.geojson
```

La capa base se conserva sin cambios en
`src/sigrif/data/cerros_sectores_valparaiso_region.geojson`. El reporte de
cobertura de la última ejecución está en `ml/official_data_coverage.json`.

## Resumen de la ejecución

| Dato | Fuente | Cobertura | Resultado |
|---|---|---|---|
| Uso de suelo y vegetación | CONAF, Catastro de Uso de Suelo y Vegetación 2019, capa IDE SMA `Biodiversidad/10` | 560/560 zonas con cobertura | `vegetation` oficial; cobertura media 99,44 % |
| Incendios 2010-2025 | CONAF, ocurrencia de incendios por temporada, IDE Minagri | 560/560 zonas; 341 con al menos un evento | 4.650 puntos de inicio asignados |
| Pendiente | SRTM 30 m vía OpenTopoData | 560/560 zonas | `slope` aproximada; 7.194 muestras válidas |

Fecha de consulta: **2026-11-13**. Fecha de los datos: catastro CONAF 2019;
temporadas de incendios 2010-2011 a 2024-2025; SRTM (misión del año 2000).

## Fuentes y URLs

### 1. CONAF: uso de suelo y vegetación

- Servicio: `https://ideserver.sma.gob.cl/arcgis/rest/services/IDE/Biodiversidad/MapServer/10`
- Metadatos: capa `V Región de Valparaíso`, catastro extraído del SIT de CONAF,
  copyright “Corporación Nacional Forestal (2019)”.
- Consulta utilizada: `where=CODREG='05'`, `outFields=OBJECTID,USO,SUBUSO,SUPERF_HA,NOM_COM,CODREG`,
  `returnGeometry=true`, `geometryPrecision=5`, `maxAllowableOffset=0.0001`,
  paginada de 1.000 en 1.000 con `resultOffset`.
- Descarga: 65.344 polígonos reportados por el servicio; 65.343 quedaron en la
  cache tras descartar una geometría vacía.
- El filtro espacial nativo del servicio (`geometry` + `esriSpatialRelIntersects`)
  respondió de forma inconsistente durante las pruebas. Por eso se descargó la
  región completa por `CODREG='05'` y el recorte por zona se hace localmente con
  `shapely`. Esto evita sobrecontar superficies y no depende del índice espacial
  del servidor.

### 2. CONAF: ocurrencia de incendios

- Catálogo de descarga: `https://ide.minagri.gob.cl/descarga-de-capas-shp/desastres/`
- Archivos usados (formato `.rar`, shapefile de puntos):
  `https://ide.minagri.gob.cl/wp-content/uploads/DESCARGAS/CAPAS/DESASTRES/INCENDIOS_FORESTALES_CONAF/if_temporada_<temporada>.rar`
- Temporadas: `2010_2011`, `2011_2012`, …, `2024_2025` (15 archivos).
- Los archivos están en UTM 19S, excepto `2024_2025`, que viene en WGS84
  geográfico. El script detecta la proyección desde el `.prj`.
- Los puntos son **puntos de inicio** reportados por CONAF, no el perímetro ni
  el área quemada. Un mismo incendio puede tener más de un registro si CONAF
  publicó más de un punto para la misma temporada.
- Se intentó localizar la capa del catálogo 42633 del Geoportal de Chile
  (`https://geoportal.cl/geoportal/catalog/42633`), pero el catálogo redirige a
  login y no entrega la descarga sin sesión. Se usó la capa oficial de
  ocurrencia publicada por IDE Minagri, que proviene de la misma fuente CONAF.
- Se filtraron los puntos a un bounding box regional amplio
  (`lon -72,5..-69,5`, `lat -34,5..-31,5`) y luego se contaron por intersección
  espacial con cada zona. Ese bounding box puede incluir bordes de regiones
  vecinas; el conteo final solo considera las 560 zonas operativas. Quedaron
  20.285 puntos en el área de descarga y 4.650 dentro de las zonas.

### 3. DEM y pendiente

- Servicio: `https://api.opentopodata.org/v1/srtm30m`
- Dataset: SRTM 30 m (NASA/NGA, año 2000), un punto por consulta.
- Muestreo: grilla de 5×5 sobre la zona; si la zona es pequeña (lado mayor
  menor a ~600 m) o muy estrecha, se muestrea un buffer de 0,002° (~200 m)
  alrededor. Se conservan hasta 16 puntos por zona.
- Pendiente: ajuste por mínimos cuadrados de un plano local `z = a·x + b·y + c`
  en UTM 19S; `slope = atan(sqrt(a² + b²))` en grados.
- Puntos con elevación nula fuera de la zona se descartan porque SRTM devuelve
  0 en el mar. Se obtuvieron 7.196 muestras, 7.194 válidas y 2 descartadas.
- Esta pendiente es una **aproximación geomorfológica**, no un producto oficial
  de pendiente. Un plano local suaviza quebradas y taludes.

## Método

### Fracciones de uso de suelo

Cada polígono CONAF se proyecta a UTM 19S, se intersecta con la zona y su área
se reparte según la categoría. Para evitar dobles conteos, cada polígono aporta
una sola vez y los solapamientos se normalizan si la suma excede la superficie
de la zona. La superficie de referencia es el área de la zona en UTM 19S.

| Categoría | USO / SUBUSO CONAF |
|---|---|
| `bosque_nativo` | Bosques / Bosque Nativo |
| `bosque_mixto` | Bosques / Bosque Mixto |
| `plantacion` | Bosques / Plantación |
| `matorral` | Praderas y Matorrales / Matorral, Matorral Arborescente, Matorral con Suculentas, Formación de Suculentas |
| `matorral` + `pradera` | Praderas y Matorrales / Matorral-Pradera (50/50) |
| `pradera` | Praderas y Matorrales / Praderas |
| `agricola` | Terrenos Agrícolas / Terreno de Uso Agrícola |
| `agricola` + `pradera` | Terrenos Agrícolas / Rotación Cultivo-Pradera (50/50) |
| `urbano` | Áreas Urbanas e Industriales / Ciudades, Pueblos, Zonas Industriales y Minería Industrial |
| `agua` | Cuerpos de Agua / Ríos, Lagos, Lagunas, Embalses, Tranques |
| `humedal` | Humedales / Vegas, Otros Terrenos Húmedos, Vegetación Herbácea en Orillas de Ríos |
| `desprovisto` | Áreas Desprovistas de Vegetación (todos los subusos) |
| `nieve` | Nieves Eternas y Glaciares / Nieves, Glaciares |
| `otro` | Cualquier combinación no listada |

Regla de vegetación:

```
vegetation = min(1, bosque_nativo + bosque_mixto + plantacion + matorral)
```

Las fracciones se normalizan por la superficie de la zona. `pradera`,
`agricola` y `urbano` se informan por separado, pero no se suman a `vegetation`.
La categoría `urbano` incluye minería industrial porque CONAF las agrupa en el
mismo uso.

### Incendios

Para cada punto se consulta un `STRtree` de zonas y se usa `covers` (incluye
bordes). El campo `historical_fires` es el total 2010-2025. También se agregan:

- `incendios_temporadas`: cantidad de temporadas con al menos un evento.
- `incendios_ultimos_5`: eventos en 2020-2021 a 2024-2025.
- `incendios_ultima_temporada`: última temporada con un evento en la zona.

No se imputan eventos ni se usan estadísticas comunales: si una zona no tiene
puntos, el valor oficial es 0. Un punto exactamente sobre un borde compartido
puede contarse en las dos zonas; en esta corrida hubo 4.649 puntos únicos y
4.650 asignaciones (un caso de borde).

### Pendiente

Las muestras se consultan en lotes de hasta 90 puntos, con pausa de ~1,05 s
para respetar el límite de 1 consulta/s de OpenTopoData. Si un lote falla tras
los reintentos, las zonas afectadas conservan su prior y quedan marcadas como
`pendiente`.

## Cobertura exacta

| Indicador | Valor |
|---|---:|
| Zonas procesadas | 560 |
| Zonas con cobertura CONAF | 560 |
| Zonas sin cobertura CONAF | 0 |
| Cobertura CONAF media | 99,44 % |
| Cobertura CONAF mediana | 100,00 % |
| Cobertura CONAF mínima | 70,13 % |
| Zonas con cobertura CONAF < 90 % | 7 |
| Zonas con al menos un incendio | 341 |
| Zonas sin incendios (0 oficial) | 219 |
| Incendios asignados | 4.650 |
| Zonas con pendiente DEM | 560 |
| Zonas con prior por falta de DEM | 0 |
| Muestras DEM solicitadas | 7.196 |
| Muestras DEM válidas | 7.194 |
| Muestras DEM descartadas (mar) | 2 |

Distribuciones de la capa resultante:

| Variable | Mínimo | Mediana | Media | Máximo |
|---|---:|---:|---:|---:|
| `vegetation` | 0,000 | 0,00025 | 0,103 | 0,946 |
| `historical_fires` | 0 | 1 | 8,30 | 334 |
| `slope` (°) | 0,08 | 2,16 | 3,17 | 16,06 |

El máximo de incendios corresponde a `SECTOR TRANQUE DE LA LUZ` (Valparaíso),
con 334 puntos de inicio en 15 temporadas. Es un valor observado, no un error de
escala; se recomienda revisarlo antes de reentrenar el modelo.

## Propiedades de procedencia

Cada feature conserva las claves que usa el modelo (`vegetation`,
`historical_fires`, `slope`) y agrega:

| Propiedad | Contenido |
|---|---|
| `Fuente_Vegetacion` | Fuente CONAF o aviso de prior |
| `Fuente_Incendios` | Fuente CONAF/IDE Minagri o aviso de prior |
| `Fuente_Pendiente` | SRTM/OpenTopoData o aviso de prior |
| `Datos_Actualizados` | Fecha ISO de la ejecución |
| `Estado_Vegetacion` | `oficial` o `pendiente` |
| `Estado_Incendios` | `oficial` o `pendiente` |
| `Estado_Pendiente` | `oficial_aproximado` o `pendiente` |
| `vegetation_prior`, `historical_fires_prior`, `slope_prior` | Valores previos, para trazabilidad |
| `veg_<categoria>_frac` | Fracciones de uso de suelo |
| `conaf_cobertura_frac`, `conaf_poligonos` | Cobertura y cantidad de polígonos recortados |
| `incendios_temporadas`, `incendios_ultimos_5`, `incendios_ultima_temporada` | Detalle de incendios |
| `dem_muestras`, `dem_elev_media_m`, `dem_elev_min_m`, `dem_elev_max_m`, `dem_proveedor` | Detalle del DEM |
| `Nota_Vegetacion` | Solo si la cobertura CONAF es menor a 90 % |

### Trazabilidad propiedad → fuente

| Propiedad de la zona | Fuente | Campo o método |
|---|---|---|
| `vegetation` | CONAF, capa IDE SMA 10 | `USO`/`SUBUSO` → fracciones; `bosque_nativo + bosque_mixto + plantacion + matorral` |
| `veg_bosque_nativo_frac`, `veg_bosque_mixto_frac`, `veg_plantacion_frac`, `veg_matorral_frac`, `veg_pradera_frac`, `veg_agricola_frac`, `veg_urbano_frac` | CONAF | área del polígono recortado a la zona / área de la zona |
| `conaf_cobertura_frac` | CONAF | suma de áreas recortadas / área de la zona (máximo 1) |
| `conaf_poligonos` | CONAF | cantidad de polígonos que intersectan la zona |
| `historical_fires` | CONAF, ocurrencia 2010-2025 | conteo de puntos de inicio dentro de la zona |
| `incendios_temporadas`, `incendios_ultimos_5`, `incendios_ultima_temporada` | CONAF | temporada del punto (`if_temporada_<temporada>.rar`) |
| `slope` | SRTM 30 m, OpenTopoData | ajuste de plano local sobre 6-16 muestras |
| `dem_muestras`, `dem_elev_media_m`, `dem_elev_min_m`, `dem_elev_max_m` | SRTM 30 m | elevaciones puntuales del API |
| `Estado_*`, `Fuente_*` | — | resultado de la corrida y disponibilidad de la fuente |

## Limitaciones

1. **El catastro CONAF es de 2019**, no de 2025. Los cambios de uso posteriores
   (incluidos los incendios de 2024) no están reflejados.
2. **Geometría simplificada**: se solicitó `maxAllowableOffset=0.0001°` (~11 m)
   para reducir el volumen. Las fracciones son aproximadas a esa escala.
3. **Zonas urbanas pequeñas**: muchas zonas miden menos de 1 km²; el DEM SRTM
   de 30 m y el plano local no resuelven taludes internos. La pendiente debe
   leerse como una media del entorno, no como pendiente de ladera.
4. **Incendios**: son puntos de inicio, no áreas quemadas. No se deduplicaron
   registros dentro de una temporada; se cuenta cada punto publicado.
5. **Escala de `historical_fires`**: pasó de un prior de 5 por comuna a conteos
   reales de 0-334 por zona. El modelo actual fue entrenado con datos sintéticos;
   este cambio de escala requiere reentrenamiento y validación.
6. **Vegetación urbana**: `vegetation` solo suma las clases CONAF de bosque,
   plantación y matorral. Los árboles urbanos, jardines y parques no se
   contabilizan, por lo que 276 zonas quedan en 0. Es una limitación de la regla,
   no un error de intersección.
7. **Categorías mixtas**: `Matorral-Pradera` y `Rotación Cultivo-Pradera` se
   reparten 50/50. Es una convención documentada, no una medición de campo.
8. **Sin cobertura oficial de pendiente**: no se usó un producto oficial de
   pendiente; SRTM + plano local es una aproximación reproducible.
9. **Servicios externos**: la disponibilidad de IDE SMA, IDE Minagri y
   OpenTopoData puede cambiar. El script falla de forma controlada y conserva
   los priors, marcando `pendiente`.
10. **No se usaron estadísticas comunales de incendios**: no fue necesario
    porque se obtuvieron los puntos por temporada. No se inventaron eventos.

## Reproducción

```bash
# Muestra de 5 zonas
uv run python scripts/enrich_official_data.py --source all --limit 5 \
  --output /tmp/opencode/sample_oficial.geojson \
  --report /tmp/opencode/sample_report.json

# Capa completa
uv run python scripts/enrich_official_data.py --source all

# Solo una fuente
uv run python scripts/enrich_official_data.py --source conaf
uv run python scripts/enrich_official_data.py --source fires
uv run python scripts/enrich_official_data.py --source dem
```

La cache queda en `ml/cache/` (CONAF, incendios y DEM) y no se versiona. Los
archivos `.rar` de incendios requieren `7z`, `unrar` o `bsdtar` para extraerse.
Para forzar una reconsulta:

```bash
uv run python scripts/enrich_official_data.py --source all --refresh
```

## Activación en el worker

`src/sigrif/worker/main.py` usa automáticamente
`cerros_sectores_valparaiso_region_oficial.geojson` si existe; si no, cae en la
capa base. Las bases de datos ya sembradas conservan los valores antiguos hasta
que se vuelva a ejecutar el seed de zonas.
