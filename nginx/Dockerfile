FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh
COPY html /usr/share/nginx/html

RUN chmod +x /entrypoint.sh

ENV API_HOST=api:8000
ENV LISTEN_PORT=80

ENTRYPOINT ["/entrypoint.sh"]
