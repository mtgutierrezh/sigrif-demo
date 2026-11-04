FROM node:22-alpine AS frontend

WORKDIR /frontend

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./

ARG VITE_API_BASE_URL=""
ARG VITE_COGNITO_AUTHORITY=""
ARG VITE_COGNITO_CLIENT_ID=""
ARG VITE_COGNITO_REDIRECT_URI=""

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_COGNITO_AUTHORITY=${VITE_COGNITO_AUTHORITY}
ENV VITE_COGNITO_CLIENT_ID=${VITE_COGNITO_CLIENT_ID}
ENV VITE_COGNITO_REDIRECT_URI=${VITE_COGNITO_REDIRECT_URI}

RUN pnpm build

FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY nginx/nginx.conf.template /etc/nginx/nginx.conf.template
COPY nginx/nginx.prod.http.conf /etc/nginx/nginx.prod.http.conf
COPY nginx/nginx.prod.https.conf /etc/nginx/nginx.prod.https.conf
COPY nginx/entrypoint.sh /entrypoint.sh
COPY --from=frontend /frontend/dist /usr/share/nginx/html

RUN chmod +x /entrypoint.sh

ENV API_HOST=api:8000
ENV LISTEN_PORT=80

ENTRYPOINT ["/entrypoint.sh"]
