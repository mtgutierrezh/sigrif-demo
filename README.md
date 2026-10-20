# SIGRIF Demo

Demo funcional del sistema de riesgo de incendios forestales para la Region de Valparaiso. El objetivo es mostrar el flujo completo con datos sinteticos: una lectura simulada entra por la API, se publica en SNS, la consume el Servicio IA desde SQS y actualiza el nivel de riesgo en PostGIS. El frontend se incorpora en una etapa posterior.

## Arquitectura

- Nginx recibe el trafico y balancea hacia la API con `least_conn`.
- API FastAPI expone zonas, simulacion y salud; valida permisos con Cognito en produccion.
- Servicio IA consume SQS, predice con Random Forest y actualiza PostGIS.
- Worker ETL siembra zonas y puede ejecutarse como tarea puntual.
- PostgreSQL 16 + PostGIS almacena geometrias y lecturas.
- SNS + SQS + DLQ desacoplan ingesta e inferencia.
- CloudWatch concentra logs y metricas en AWS.

Una sola imagen contiene los comandos `api`, `ia` y `worker`. Nginx usa una imagen propia.

## Inicio local

Requisitos: Docker, Docker Compose y `uv`.

```bash
make install
make up
make seed
make smoke
```

La demo queda en `http://localhost:8080`. La API directa esta en `http://localhost:8000`.

Si el entorno no soporta redes bridge de Docker (por ejemplo, una VM sin `CAP_NET_ADMIN`), usa el compose con `network_mode: host`:

```bash
make up-host
make seed-host
make smoke
make down-host
```

En ese modo, la base de datos escucha en el puerto 55432, la API en 8000, el Servicio IA en 8001, Nginx en 8080 y LocalStack en 4566.

Endpoints principales:

- `GET /health`
- `GET /metrics`
- `GET /api/v1/zones`
- `GET /api/v1/zones/{id}`
- `POST /api/v1/simulate`

`POST /api/v1/simulate` genera una lectura sintetica, la publica en SNS y responde `202`. El Servicio IA actualiza el riesgo en segundos; se puede verificar con `GET /api/v1/zones`.

## Calidad

```bash
make verify
```

Ejecuta lint, pruebas con cobertura minima de 60 %, analisis de seguridad y la regla de codigo sin comentarios. Las pruebas no requieren AWS ni contenedores.

## Despliegue en AWS

Requisitos: Terraform, AWS CLI y credenciales con permisos sobre ECS, ECR, RDS, SNS, SQS, Cognito, CloudWatch e IAM.

```bash
make demo-up
make demo-url
make demo-down
```

`demo-up` crea la infraestructura, publica las imagenes y fuerza el despliegue. `demo-url` obtiene la IP publica de Nginx. `demo-down` destruye todo.

La demo es deliberadamente simple: una tarea por servicio, RDS Single-AZ, subredes publicas sin NAT y sin replicas. El diseno de alta disponibilidad esta documentado en la entrega EP2, pero no se despliega para evitar costos. La estimacion es de USD 0,42 por una ventana de cuatro horas y de USD 76 al mes si se deja encendida. Destruir al terminar.

## Seguridad

- Sin secretos en el repositorio; `.env.example` solo documenta variables.
- Contenedores non-root y dependencias fijadas.
- Security groups con minimo privilegio; RDS en subred privada.
- Cognito con grupos `usuarios` y `operadores` en el diseno de produccion.
- TLS y ACM se configuran al publicar el dominio; la demo local usa HTTP.

## Estructura

```text
src/sigrif/        API, Servicio IA, worker y logica compartida
tests/             Pruebas unitarias y de contrato
nginx/             Imagen y configuracion del balanceador
scripts/           Semilla, smoke test y verificacion de estilo
infra/             Terraform de la demo en AWS
```

## Identidad Git

El repositorio debe publicarse con la cuenta educativa. Antes del primer commit:

```bash
git config user.name "Nombre Apellido"
git config user.email "correo@institucional.cl"
git remote add origin git@github.com-usuario:usuario/sigrif-demo.git
```

Verificar con `git config --get user.email` antes de cada push.
