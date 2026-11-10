# Despliegue free-tier

Esta carpeta reemplaza el despliegue ECS/Fargate de la primera versión por una
instancia EC2 con Docker Compose. La decisión busca cumplir la guía 3.1.5 sin
consumir el crédito de la cuenta en servicios administrados que el prototipo
todavía no necesita.

## Qué crea

| Recurso | Uso |
|---|---|
| EC2 `t3.micro` | Ejecuta Nginx, API, IA, PostGIS y el job de seed. |
| Security group | Abre 80 y 443; no abre SSH. |
| Rol IAM + SSM | Acceso administrativo por Session Manager, sin llave SSH. |
| Permiso Bedrock | La instancia invoca `amazon.nova-lite-v1:0` para el OCR, sin claves estáticas. |
| S3 | Dataset, artefacto del modelo y bundles de despliegue. |
| Cognito | User pool, client y grupos `usuarios`/`operadores`. |
| CloudWatch | Log groups, alarma de CPU y de status check. |
| AWS Budgets | Aviso opcional al 80% y 100% del límite mensual. |
| Rol OIDC GitHub | GitHub Actions puede desplegar sin claves estáticas. |

La instancia usa la VPC por defecto y una subred pública. No se crea NAT,
ALB, RDS, ECR, CloudFront ni Route 53.

Si los paquetes de GHCR quedan privados, completar `ghcr_username` y
`ghcr_token` (con `read:packages`). El servidor guarda el token en
`/opt/sigrif/ghcr_token` con permisos 600 y lo usa solo para `docker login`
antes de descargar las imágenes.

## Uso

```bash
cd infra/free-tier
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

El estado queda local en `terraform.tfstate`. Para trabajo en equipo conviene
moverlo a un backend S3 con bloqueo en DynamoDB; el archivo no se versiona.

Al terminar:

```bash
terraform destroy
```

## Después del apply

1. Crear el subdominio en DuckDNS y apuntarlo a la IP pública. El `user_data`
   instala un timer que actualiza la IP cada cinco minutos.
2. Crear los usuarios de prueba con `scripts/cognito_users.sh` usando el
   `cognito_user_pool_id` que entrega Terraform:

   ```bash
   COGNITO_USER_POOL_ID=<pool_id> \
   COGNITO_TEST_PASSWORD='<clave>' \
   bash scripts/cognito_users.sh
   ```
3. Publicar el artefacto del modelo:

   ```bash
   aws s3 cp artifacts/risk_model.joblib \
     s3://<artifact_bucket>/models/risk_model.joblib
   aws s3 cp ml/model_metadata.json \
     s3://<artifact_bucket>/models/model_metadata.json
   aws s3 cp ml/metrics.json \
     s3://<artifact_bucket>/models/metrics.json
   ```

4. Ejecutar el workflow `deploy` de GitHub Actions. En el repositorio se
   configuran las variables `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`,
   `INSTANCE_ID`, `S3_BUCKET`, `DEPLOY_ENABLED=true` y las `VITE_*` del
   frontend. El workflow no usa claves estáticas: asume el rol por OIDC.
   Verificar que `amazon.nova-lite-v1:0` esté habilitado en Bedrock para la
   cuenta y la región. Si no lo está, el OCR responde `503` y el operador puede
   escribir el texto manualmente; no se inventa una transcripción.
5. Emitir el certificado TLS una vez que Nginx esté arriba:

   ```bash
   aws ssm start-session --target <instance_id>
   sudo bash /opt/sigrif/release/scripts/init_letsencrypt.sh
   ```

## Costos

`t3.micro`, 20 GB de gp3, una IP pública y los logs consumen el crédito de la
cuenta nueva. La estimación de trabajo es USD 0 a 4 mensuales dentro del plan
gratuito; si el crédito no cubre algún recurso, el gasto sigue siendo bajo.
Configurar `budget_email` y destruir al final de la demostración.

## Límites

- Una sola instancia: si EC2 falla, el servicio se cae. Es aceptable para el
  prototipo y queda documentado como evolución hacia ECS o Multi-AZ.
- El blue-green protege el despliegue de la API, no la caída de la máquina.
- La base de datos vive en el mismo host; los respaldos se copian a S3.
- `t3.micro` tiene 1 GB de RAM; el `user_data` crea 2 GB de swap.
