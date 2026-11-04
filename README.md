# SIGRIF

Demo funcional de riesgo de incendios forestales para Valparaíso. Incluye API en FastAPI, PostgreSQL/PostGIS, mensajería SNS/SQS, un servicio de IA con Random Forest, Nginx y un frontend en React.

Los datos de riesgo son sintéticos para la demo. Los polígonos forestales provienen del catastro de uso de suelo y vegetación de CONAF.

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
- `operadores`: además puede ejecutar simulaciones.

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
| GET | `/api/v1/cells` | Celdas H3 de combustible |
| GET | `/api/v1/status` | Estado operativo |
| GET | `/api/v1/version` | Versión de API, modelo y color activo |
| POST | `/api/v1/simulate?zone_id={id}` | Genera una lectura sintética |
| POST | `/api/v1/zones/{id}/evaluate` | Inferencia síncrona, explicación y prescripción |

El servicio de IA expone además `POST /predict` y `GET /model` en el puerto
8001. La API pública es la que orquesta: autentica, valida, llama a la IA,
construye la prescripción y persiste la lectura.

Con `AUTH_ENABLED=true`, la lectura de zonas, estado, celdas e historial es pública. `POST /simulate` y `POST /api/v1/zones/{id}/evaluate` requieren un token de Cognito y el grupo `operadores`.

Ejemplo de evaluación:

```bash
curl -X POST http://localhost:8080/api/v1/zones/1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"temperature":32,"humidity":25,"wind_speed":48,"vegetation":0.7,"historical_fires":6,"slope":28}'
```

El `id` debe ser uno real de `GET /api/v1/zones`; en la demo cargada suele
empezar en 7. La respuesta incluye nivel, probabilidad, factores, escenario y
las acciones prescriptivas.

## Datos de la demo

- 54 cerros y sectores de Valparaíso.
- 467 celdas H3 con combustible derivado de CONAF.
- 1.978 polígonos forestales: bosque nativo, plantación, matorral y pradera.
- Riesgo sintético para demostración. No reemplaza las alertas de CONAF ni SENAPRED.

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

El despliegue vigente es EC2 `t3.micro` + Docker Compose, pensado para el plan
gratuito. La infraestructura está en `infra/free-tier/` y usa `us-east-2`:

```bash
cd infra/free-tier
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

El servidor ejecuta Nginx + Certbot, API blue/green, servicio IA, PostGIS y un
job de seed. No usa ECS, ALB, RDS, ECR ni NAT. El acceso administrativo es por
SSM Session Manager, sin abrir SSH.

Los atajos del `Makefile` son:

```bash
make free-plan
make free-up
make publish-model BUCKET=sigrif-prod-...
make free-down
```

El pipeline `.github/workflows/deploy.yml` construye las imágenes, las publica
en GHCR y envía el bundle por SSM. Si los paquetes quedan privados, Terraform
recibe `ghcr_username` y `ghcr_token` para que la instancia pueda descargarlos. Requiere las variables `AWS_DEPLOY_ROLE_ARN`,
`AWS_REGION`, `INSTANCE_ID`, `S3_BUCKET` y las `VITE_*` del frontend. El detalle
está en `infra/free-tier/README.md`.

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
