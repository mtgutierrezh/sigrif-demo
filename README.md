# SIGRIF

Demo funcional de riesgo de incendios forestales para la Región de Valparaíso. Incluye API en FastAPI, PostgreSQL/PostGIS, mensajería SNS/SQS, ingesta meteorológica DMC con respaldo Open-Meteo, un servicio de IA con Random Forest, Nginx, Prometheus/Grafana y un frontend en React.

Las etiquetas de entrenamiento son académicas y el modelo no reemplaza a CONAF ni SENAPRED. Los polígonos forestales provienen del catastro de uso de suelo y vegetación de CONAF; las lecturas meteorológicas de producción se obtienen de la Red EMA de la DMC.

## Requisitos

- Docker y Docker Compose
- Python 3.12 y `uv`
- Node.js 20 o superior y `pnpm` 9

## Inicio rápido

```bash
cp .env.example .env
make install
make demo-local
```

`make demo-local` levanta PostGIS, LocalStack, API, IA, Nginx, Prometheus y Grafana; carga los sectores y las celdas de riesgo; y ejecuta una prueba de humo.

Si Docker soporta redes bridge, usa la variante estándar:

```bash
make up
make seed
make smoke
```

En este entorno se usa `docker-compose.host.yml` porque el daemon no crea redes bridge. La base de datos queda en el puerto **55432**.

Detener todo:

```bash
make down-host
```

## Modelo y entrenamiento

El clasificador es un Random Forest de scikit-learn con seis variables:
temperatura, humedad, viento, vegetación combustible, incendios históricos y
pendiente. El artefacto se genera aparte del arranque del contenedor:

```bash
make train
```

El comando deja el dataset en `data/training/`, el modelo en `artifacts/` y los
metadatos y métricas en `ml/`. La versión vigente es `random-forest-0.2.0`.
Revisa `ml/DATASET_CARD.md` y `ml/MODEL_CARD.md` antes de usar las métricas: las
etiquetas son académicas y validan la regla de entrenamiento, no el riesgo real.

## Frontend

El frontend de la demo se sirve desde el contenedor Nginx en
`http://localhost:8080`, con el build de React ya incluido. Vite queda solo para
desarrollo:

```bash
cp frontend/.env.example frontend/.env.local
pnpm --dir frontend install
pnpm --dir frontend dev
```

Abre `http://localhost:5173`. Para el contenedor, las variables `VITE_*` se
pasan como build args desde `.env`; no se leen de `frontend/.env.local`.

Sin variables `VITE_COGNITO_*`, el frontend usa una sesión local. En ese caso la
API debe tener `AUTH_ENABLED=false`.

## Servicios

| Servicio | URL |
|---|---|
| Nginx + frontend + API | `http://localhost:8080` |
| API directa | `http://localhost:8000` |
| Servicio IA | `http://localhost:8001` |
| Vite (solo desarrollo) | `http://localhost:5173` |
| Grafana | `http://localhost:3000` |
| Prometheus | `http://localhost:9090` |

Grafana usa `admin` y la contraseña definida en `GRAFANA_ADMIN_PASSWORD` (por defecto `admin`). El dashboard se llama **SIGRIF · Operación**.

## Autenticación con Cognito

Es opcional para la demo local. Para el contenedor Nginx, las variables del
frontend se pasan como build args desde `.env`:

```dotenv
# .env
AUTH_ENABLED=true
COGNITO_REGION=us-east-2
COGNITO_USER_POOL_ID=us-east-2_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx

VITE_API_BASE_URL=http://localhost:8080
VITE_COGNITO_AUTHORITY=https://cognito-idp.us-east-2.amazonaws.com/us-east-2_xxxxxxxxx
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_COGNITO_REDIRECT_URI=http://localhost:8080/auth/callback
```

Para Vite en desarrollo, esas mismas variables van en `frontend/.env.local` y
el redirect puede ser `http://localhost:5173/auth/callback`.

Crea los usuarios de prueba:

```bash
COGNITO_USER_POOL_ID=us-east-2_xxxxxxxxx \
COGNITO_TEST_PASSWORD='<clave>' \
bash scripts/cognito_users.sh
```

Grupos:

- `usuarios`: consulta de zonas, riesgo e historial.
- `operadores`: además puede simular lecturas, evaluar escenarios y digitalizar fichas de terreno.

Credenciales de prueba:

| Usuario | Contraseña | Grupo |
|---|---|---|
| `usuario@demo.sigrif.cl` | `SigrifDemo2026` | `usuarios` |
| `operador@demo.sigrif.cl` | `SigrifDemo2026` | `operadores` |

Solo para la demo. Cambiar en un despliegue real.

## Endpoints

| Método | Ruta | Uso |
|---|---|---|
| GET | `/health` | Estado del servicio |
| GET | `/metrics` | Métricas Prometheus |
| GET | `/api/v1/zones` | Lista de sectores con riesgo |
| GET | `/api/v1/zones/{id}` | Detalle de un sector |
| GET | `/api/v1/zones/{id}/history` | Historial de riesgo |
| GET | `/api/v1/cells` | Celdas H3 de combustible (límite configurable) |
| GET | `/api/v1/cells/bbox?min_lon=&min_lat=&max_lon=&max_lat=&limit=` | Malla H3 dentro del visor |
| GET | `/api/v1/status` | Estado operativo |
| GET | `/api/v1/version` | Versión de API, modelo y color activo |
| GET | `/api/v1/model` | Model card en vivo (operadores) |
| GET | `/api/v1/evaluations` | Evaluaciones recientes (operadores) |
| GET | `/api/v1/zones/{id}/evaluations` | Evaluaciones de una zona (operadores) |
| GET | `/api/v1/ops/overview` | Resumen operativo, frescura, cola y drift (operadores) |
| GET | `/api/v1/ops/alerts` | Zonas en nivel Alto (operadores) |
| GET | `/api/v1/ops/ingestion` | Últimas corridas de ingesta (operadores) |
| GET | `/api/v1/ops/drift` | PSI por variable (operadores) |
| POST | `/api/v1/ops/ingest?provider=auto` | Dispara una ingesta manual (operadores) |
| POST | `/api/v1/simulate?zone_id={id}` | Genera una lectura sintética |
| POST | `/api/v1/zones/{id}/evaluate` | Inferencia síncrona, explicación y prescripción |
| POST | `/api/v1/field-reports/ocr` | Extrae texto de una ficha de terreno (multipart) |
| POST | `/api/v1/zones/{id}/field-reports` | Guarda el texto revisado por el operador |
| GET | `/api/v1/zones/{id}/field-reports` | Lista los reportes confirmados de la zona |
| GET | `/api/v1/alerts` | Lista alertas operativas (operador) |
| PATCH | `/api/v1/alerts/{id}` | Actualiza estado, responsable o comentario (operador) |
| GET | `/api/v1/zones/{id}/report.csv` | Reporte CSV de la zona (operador) |
| GET | `/api/v1/zones/{id}/report.pdf` | Reporte PDF de la zona (operador) |
| GET | `/api/v1/reports/zones.csv` | Reporte CSV consolidado de zonas (operador) |

El servicio de IA expone además `POST /predict`, `GET /model` y `POST /ocr` en
el puerto 8001. La API pública es la que orquesta: autentica, valida, llama a la
IA, construye la prescripción y persiste la lectura o el reporte confirmado.

La API también actúa como AI Gateway. Genera o hereda `X-Request-ID`, lo
devuelve en la respuesta y lo reenvía al servicio IA. Si la inferencia falla por
un error 5xx o timeout, realiza hasta tres intentos con backoff exponencial y
jitter; un error 4xx no se reintenta. Después de tres fallos consecutivos abre un
circuit breaker durante 30 segundos y responde `503` con `Retry-After: 5` en
lugar de inventar una predicción. Los detalles están en `src/sigrif/ia/client.py`.

Con `AUTH_ENABLED=true`, la lectura de zonas, estado, celdas e historial es pública. `POST /simulate`, `POST /api/v1/zones/{id}/evaluate`, el OCR y el guardado de reportes requieren un token de Cognito y el grupo `operadores`.

Ejemplo de evaluación:

```bash
curl -X POST http://localhost:8080/api/v1/zones/1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"temperature":32,"humidity":25,"wind_speed":48,"vegetation":0.7,"historical_fires":6,"slope":28}'
```

El `id` debe ser uno real de `GET /api/v1/zones`; en la demo cargada suele
empezar en 7. La respuesta incluye nivel, probabilidad, factores, escenario y
las acciones prescriptivas.

### OCR de fichas de terreno

La guía 3.2.4 pedía OCR con Bedrock y Claude 3 Haiku. Como ese modelo alcanzó
su fin de vida el 10/09/2026 y no está disponible en `us-east-2`, usamos
`amazon.nova-lite-v1:0` con la API Converse. El flujo es: el operador sube una
foto JPEG, PNG o WebP; el servicio IA extrae el texto; el operador lo corrige y
lo guarda asociado a la zona. La imagen no se almacena.

```bash
curl -X POST http://localhost:8080/api/v1/field-reports/ocr \
  -F 'file=@ficha.png;type=image/png'

curl -X POST http://localhost:8080/api/v1/zones/7/field-reports \
  -H 'Content-Type: application/json' \
  -d '{"extracted_text":"PTCL-23\nCHILE","confirmed_text":"PTCL-23\nCHILE","model_id":"amazon.nova-lite-v1:0","source_filename":"ficha.png","content_type":"image/png","size_bytes":1234}'
```

En local `BEDROCK_ENABLED=false` para no exigir credenciales AWS. En EC2 se
habilita con el rol IAM de la instancia; no se usan claves en `.env`. El OCR
rechaza archivos de más de 5 MB, valida la firma real de la imagen y responde
`503` con `Retry-After` si Bedrock no está disponible.

## Operaciones y monitoreo

El panel `/operaciones` está disponible solo para el grupo `operadores`. Muestra la frescura de los datos, la fuente de la última lectura, la distribución de riesgo, la profundidad de la cola SQS, el drift PSI por variable, las últimas corridas de ingesta y las zonas en alerta. El usuario final del grupo `usuarios` no ve este panel ni puede llamar a los endpoints `/ops`.

La ingesta se ejecuta cada 15 minutos con DMC como fuente principal y Open-Meteo como respaldo. Si no hay datos nuevos, no se reprocesa la misma observación. En producción el bus es SNS + SQS: la ingesta publica `lectura.creada`, el consumidor del servicio IA evalúa y persiste la lectura y su `Evaluation`. Las alertas de nivel Alto se publican en el tópico SNS confirmado, con un cooldown de seis horas por zona.

Grafana se publica en `https://<dominio>/grafana/` y usa Prometheus para las métricas de API, IA, ingesta, cola, frescura, alertas y drift. Prometheus y Grafana también están disponibles en local en los puertos 9090 y 3000.

El **centro de alertas** vive en `/alertas` y en `/operaciones`. Cada evaluación de nivel Alto crea o actualiza una alerta abierta; el operador puede asignarle responsable, cambiar su estado (`nueva`, `en_revision`, `cerrada`), agregar comentarios y revisar el historial de eventos. La alerta SNS se mantiene como notificación externa.

Los reportes PDF y CSV incluyen nivel, score, fuente, fecha, factores, escenario y prescripción. Se descargan desde el panel de zona y desde `/operaciones`; el CSV consolidado usa BOM para abrirlo directamente en Excel.

## Datos de la demo

La capa de nombres combina los 54 sectores municipales de Valparaíso, nombres
referenciales de OpenStreetMap/Photon para zonas censales y localidades del
Censo 2017. Cada zona declara `zone_type`, `name_source` y `name_official`; los
nombres no oficiales se muestran como referencia y no como límites oficiales.

- 54 sectores urbanos de Valparaíso, 506 zonas censales de 35 comunas continentales, 2 zonas de Isla de Pascua y 1 polígono de Juan Fernández (563 zonas, 38/38 comunas).
- 24.596 celdas H3 res 8 para la Región de Valparaíso continental, con combustible calculado desde CONAF 2019 y recorte al territorio comunal.
- 1.978 polígonos forestales: bosque nativo, plantación, matorral y pradera.
- Variables estáticas por zona: CONAF 2019 (uso de suelo y vegetación), incendios históricos 2010–2025 y pendiente SRTM 30 m.
- Variables meteorológicas reales de la Red EMA de la DMC, actualizadas cada 15 minutos; Open-Meteo queda como respaldo.
- Las etiquetas del modelo son académicas: validan la regla de entrenamiento, no el riesgo real. El sistema no reemplaza las alertas de CONAF ni SENAPRED.

## Calidad

```bash
make verify
pnpm --dir frontend lint
pnpm --dir frontend test
pnpm --dir frontend build
make test-e2e
```

`make verify` ejecuta ruff, mypy, pytest con cobertura, bandit, pip-audit y la revisión de comentarios. `make test-e2e` requiere el stack levantado; si `AUTH_ENABLED=true`, define `SIGRIF_E2E_TOKEN` con un token de Cognito del grupo `operadores`.

## Despliegue en AWS

El despliegue vigente es EC2 `t3.small` + Docker Compose durante la evaluación,
pensado para el plan gratuito. Está aplicado en `us-east-2` y responde en
<https://sigrif-valparaiso.duckdns.org> con certificado Let's Encrypt. La memoria
extra permite ejecutar ingesta, Prometheus, Grafana y node-exporter junto al
stack principal; al terminar la evaluación se puede volver a `t3.micro`.

La infraestructura está en `infra/free-tier/`:

```bash
cd infra/free-tier
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

El servidor ejecuta Nginx + Certbot, API blue/green, servicio IA, PostGIS, un
job de seed, la ingesta DMC/Open-Meteo, Prometheus, Grafana y node-exporter. La
cola SNS/SQS de lecturas vive en AWS, fuera de la instancia. La instancia usa
una Elastic IP para mantener el DNS estable. No usa ECS, ALB, RDS, ECR ni NAT.
El acceso administrativo es por SSM Session Manager, sin abrir SSH.

Los atajos del `Makefile` son:

```bash
make free-plan
make free-up
make publish-model BUCKET=sigrif-prod-...
make free-down
```

El pipeline `.github/workflows/deploy.yml` construye las imágenes, las publica
en GHCR y envía el bundle por SSM. En esta cuenta el tramo automático por OIDC
está bloqueado por una política SCP de la organización. Por decisión del equipo
no se insistirá en esta entrega: el CI de calidad y build sigue funcionando y
el despliegue se ejecuta por SSM con la sesión autenticada. El tema se retomará
solo si el proyecto avanza a producción. El detalle está en
`infra/free-tier/README.md` y en
`EA3/Evidencias_3.1/3.1.5/deploy_aws/README.md`.

El stack anterior de ECS en `infra/` queda como arquitectura objetivo para
cuando haya usuarios concurrentes o presupuesto para alta disponibilidad. Para
la entrega se documenta como evolución, no como despliegue activo.

`make demo-down` ya no se usa para el free-tier; el apagado es
`cd infra/free-tier && terraform destroy`.

## Estructura

```
src/sigrif/       API, servicio IA y worker
labs/3.1.2/       Laboratorio aislado de predicción y prescripción
frontend/         React, Vite y Leaflet
nginx/            Entrada y balanceo
infra/            Terraform ECS (arquitectura objetivo)
infra/free-tier/  Terraform EC2 + Compose del despliegue vigente
docker-compose.prod.yml  Compose de producción
data/training/    Dataset sintético de entrenamiento
ml/               Dataset card, model card, metadatos y métricas
artifacts/        Artefacto del modelo (no versionado)
scripts/          Entrenamiento, seed, smoke, usuarios y superficie de riesgo
observability/    Prometheus y Grafana
tests/            Pruebas del backend
```

## Problemas frecuentes

- **401 en la API**: `AUTH_ENABLED` y las variables `VITE_COGNITO_*` deben corresponder al mismo user pool. Inicia sesión y recarga.
- **No levanta por red bridge**: usa `make demo-local` o `make up-host`.
- **Puerto 5432 ocupado**: el compose host usa 55432; no cambies ese valor.

## Combustible regional

Cada zona expone el desglose de combustible derivado de CONAF 2019: bosque
nativo, plantación, matorral, pradera, agrícola y urbano. El panel de zona
muestra las fracciones y el mapa permite alternar entre **Riesgo** y
**Combustible**; el color representa el combustible dominante. La capa cubre
las 563 zonas y no reemplaza la validación de terreno.

## Malla H3 regional

La malla se regenera con:

```bash
uv run python scripts/build_h3_region.py
```

El alcance por defecto es la Región de Valparaíso continental (36 comunas,
sin Isla de Pascua ni Juan Fernández). Genera 24.596 celdas H3 res 8, recorta
cada celda al polígono comunal DPA 2022 y calcula las fracciones de combustible
intersecando el catastro CONAF 2019. Las celdas sin intersección directa con
una de las 563 zonas oficiales se asocian a la zona más cercana de la misma
comuna; el detalle queda en `metadata` del GeoJSON. Las 560 zonas continentales
quedan cubiertas geométricamente por la malla.

Para generar solo el recorte de las 563 zonas (945 celdas) usa:

```bash
uv run python scripts/build_h3_region.py --scope zones
```

El visor pide únicamente el bbox visible a `/api/v1/cells/bbox` y activa la
malla desde zoom 12, con un máximo de 4.000 celdas por respuesta. Así no se
descargan las 24.596 celdas al abrir el mapa. La capa se colorea por riesgo o
por combustible y se puede ocultar desde el panel izquierdo.
