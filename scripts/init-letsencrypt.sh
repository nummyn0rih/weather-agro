#!/usr/bin/env bash
# Первичная инициализация Let's Encrypt-сертификата.
#
# Алгоритм (адаптировано из github.com/wmnnd/nginx-certbot):
#   1. Создаём self-signed «dummy»-сертификат, чтобы nginx стартанул.
#   2. Поднимаем nginx (HTTPS-блок цепляется к dummy-серту).
#   3. Удаляем dummy, запрашиваем настоящий сертификат через webroot challenge.
#   4. Перезагружаем nginx.
#
# Использование:
#   DOMAIN=example.com LETSENCRYPT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh
#   # staging (для тестов, не упирается в rate-limit):
#   STAGING=1 DOMAIN=example.com LETSENCRYPT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh
#
# Повторный запуск — безопасен (всё пересоздаётся).

set -euo pipefail

: "${DOMAIN:?DOMAIN не задан. Пример: DOMAIN=example.com ./scripts/init-letsencrypt.sh}"
: "${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL не задан}"

STAGING="${STAGING:-0}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
DATA_PATH="./letsencrypt-init"
RSA_KEY_SIZE=4096

echo ">>> Домен:       ${DOMAIN}"
echo ">>> Email:       ${LETSENCRYPT_EMAIL}"
echo ">>> Staging:     ${STAGING}"

# 1. Готовим dummy-сертификат в volume letsencrypt.
echo ">>> [1/4] Создаю dummy-сертификат для ${DOMAIN}..."
$COMPOSE run --rm --entrypoint "\
  sh -c '\
    mkdir -p /etc/letsencrypt/live/${DOMAIN} && \
    openssl req -x509 -nodes -newkey rsa:${RSA_KEY_SIZE} -days 1 \
      -keyout /etc/letsencrypt/live/${DOMAIN}/privkey.pem \
      -out /etc/letsencrypt/live/${DOMAIN}/fullchain.pem \
      -subj /CN=localhost && \
    cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem /etc/letsencrypt/live/${DOMAIN}/chain.pem'" \
  certbot

# 2. Стартуем nginx (он подхватит dummy и сможет ответить на ACME-challenge).
echo ">>> [2/4] Запускаю nginx..."
$COMPOSE up -d --force-recreate nginx

# 3. Удаляем dummy и запрашиваем настоящий сертификат.
echo ">>> [3/4] Удаляю dummy, запрашиваю реальный сертификат..."
$COMPOSE run --rm --entrypoint "\
  rm -rf /etc/letsencrypt/live/${DOMAIN} \
         /etc/letsencrypt/archive/${DOMAIN} \
         /etc/letsencrypt/renewal/${DOMAIN}.conf" certbot

STAGING_ARG=""
if [[ "${STAGING}" == "1" ]]; then
  STAGING_ARG="--staging"
fi

$COMPOSE run --rm --entrypoint "\
  certbot certonly --webroot --webroot-path=/var/www/certbot \
    ${STAGING_ARG} \
    --email ${LETSENCRYPT_EMAIL} \
    -d ${DOMAIN} \
    --rsa-key-size ${RSA_KEY_SIZE} \
    --agree-tos \
    --no-eff-email \
    --force-renewal" certbot

# 4. Перезагружаем nginx с настоящим сертификатом.
echo ">>> [4/4] Перезагружаю nginx..."
$COMPOSE exec nginx nginx -s reload

echo ">>> Готово. Проверка: curl -I https://${DOMAIN}"
