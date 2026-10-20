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

## Frontend

```bash
cp frontend/.env.example frontend/.env.local
pnpm --dir frontend install
pnpm --dir frontend dev
```

Abre `http://localhost:5173`.

Sin variables `VITE_COGNITO_*`, el frontend usa una sesión local. En ese caso la API debe tener `AUTH_ENABLED=false`.

## Servicios

| Servicio | URL |
|---|---|
| Nginx / API | `http://localhost:8080` |
| API directa | `http://localhost:8000` |
| Servicio IA | `http://localhost:8001` |
| Frontend | `http://localhost:5173` |
| Grafana | `http://localhost:3000` |
| Prometheus | `http://localhost:9090` |

Grafana usa `admin` y la contraseña definida en `GRAFANA_ADMIN_PASSWORD` (por defecto `admin`). El dashboard se llama **SIGRIF · Operación**.

## Autenticación con Cognito

Es opcional para la demo local. Para habilitarla, configura `.env` y `frontend/.env.local`:

```dotenv
# .env
AUTH_ENABLED=true
COGNITO_REGION=us-east-2
COGNITO_USER_POOL_ID=us-east-2_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

```dotenv
# frontend/.env.local
VITE_API_BASE_URL=http://localhost:8080
VITE_COGNITO_AUTHORITY=https://cognito-idp.us-east-2.amazonaws.com/us-east-2_xxxxxxxxx
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_COGNITO_REDIRECT_URI=http://localhost:5173/auth/callback
```

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
| POST | `/api/v1/simulate?zone_id={id}` | Genera una lectura sintética |

Con `AUTH_ENABLED=true`, la lectura de zonas, estado, celdas e historial es pública. Solo `POST /simulate` requiere un token de Cognito y el grupo `operadores`.

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

`make verify` ejecuta ruff, mypy, pytest con cobertura, bandit, pip-audit y la revisión de comentarios. `make test-e2e` requiere el stack levantado.

## Despliegue en AWS

Opcional. La infraestructura está en `infra/` y usa la región `us-east-2`.

```bash
make demo-up
make demo-url
make demo-down
```

`make demo-up` construye y publica las imágenes, aplica Terraform y actualiza ECS. `make demo-down` destruye los recursos para evitar costos.

## Estructura

```
src/sigrif/       API, servicio IA y worker
frontend/         React, Vite y Leaflet
nginx/            Entrada y balanceo
infra/            Terraform
scripts/          Seed, smoke, usuarios y superficie de riesgo
observability/    Prometheus y Grafana
tests/            Pruebas del backend
```

## Problemas frecuentes

- **401 en la API**: `AUTH_ENABLED` y las variables `VITE_COGNITO_*` deben corresponder al mismo user pool. Inicia sesión y recarga.
- **No levanta por red bridge**: usa `make demo-local` o `make up-host`.
- **Puerto 5432 ocupado**: el compose host usa 55432; no cambies ese valor.
