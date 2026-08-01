FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/nginx.conf
COPY docker-entrypoint-certs.sh /docker-entrypoint-certs.sh
RUN chmod +x /docker-entrypoint-certs.sh

EXPOSE 8080 8443

ENTRYPOINT ["/docker-entrypoint-certs.sh"]
