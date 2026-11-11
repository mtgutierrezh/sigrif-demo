# Despliegue free-tier

Esta carpeta reemplaza el despliegue ECS/Fargate de la primera versión por una
instancia EC2 con Docker Compose. La decisión busca cumplir la guía 3.1.5 sin
consumir el crédito de la cuenta en servicios administrados que el prototipo
todavía no necesita.

## Qué crea

| Recurso | Uso |
|---|---|
| EC2 `t3.micro` | Ejecuta Nginx, API, IA, PostGIS y el job de seed. |
| Elastic IP | Mantiene estable la IP pública usada por el DNS y TLS. |
| Security group | Abre 80 y 443; no abre SSH. |
| Rol IAM + SSM | Acceso administrativo por Session Manager, sin llave SSH. |
| Permiso Bedrock | La instancia invoca `amazon.nova-lite-v1:0` para el OCR, sin claves estáticas. |
| S3 | Dataset, artefacto del modelo y bundles de despliegue. |
| Cognito | User pool, client y grupos `usuarios`/`operadores`. |
| CloudWatch | Log groups, alarma de CPU y de status check. |
| AWS Budgets | Aviso opcional al 80% y 100% del límite mensual. |
| Rol OIDC GitHub | Opcional con `enable_github_oidc=true`; esta organización bloquea la creación del proveedor por SCP. |

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

## Estado del despliegue

El stack está aplicado en la cuenta `434661699063`, región `us-east-2`:

| Dato | Valor |
|---|---|
| URL | <https://18-224-211-162.sslip.io> |
| Instancia | `i-0a17768ef560ac55d` |
| Elastic IP | `18.224.211.162` |
| Certificado | Let's Encrypt, vence el 9 de febrero de 2027 |
| Color activo | `blue` |

El certificado se emitió con `scripts/init_letsencrypt.sh`; el script ahora
carga `images.env` para no intentar descargar una etiqueta inexistente. La
instancia arranca con `user_data` corregido: instala Docker y `unzip` sin
reemplazar `curl-minimal` y no imprime secretos en los logs.

La política SCP de la organización niega `iam:CreateOpenIDConnectProvider`; por
eso `enable_github_oidc=false` y el despliegue automático de GitHub no está
activo. Por decisión del equipo no se insistirá en esta entrega: el workflow de
CI/CD queda preparado, el despliegue se ejecuta por SSM con la sesión
autenticada y el tema se retomará solo si el proyecto avanza a producción.

El dominio `sslip.io` es temporal. Cuando el equipo entregue el subdominio y el
token DuckDNS, se actualiza `duckdns_subdomain`/`duckdns_token` en
`terraform.tfvars`, se aplica Terraform y se emite el certificado para el nuevo
nombre.

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

4. Desplegar por SSM con la sesión autenticada: empaquetar el bundle con
   `scripts/package_deploy.sh`, subirlo a S3 y ejecutar
   `scripts/ssm_deploy.sh`. El workflow de GitHub Actions queda preparado, pero
   su tramo OIDC está fuera de esta entrega por decisión del equipo, porque la
   organización bloquea la creación del proveedor. Verificar que
   `amazon.nova-lite-v1:0` esté habilitado en Bedrock para la cuenta y la
   región. Si no lo está, el OCR responde `503` y el operador puede escribir el
   texto manualmente; no se inventa una transcripción.
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
