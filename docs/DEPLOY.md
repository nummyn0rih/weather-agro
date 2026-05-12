# Deploy — VPS + HTTPS (Let's Encrypt)

Инструкция для production-развёртывания на чистом VPS.

## 0. Журнал изменений (per-task)

### 5.3 deploy note
Backend-образ нужно пересобрать после этого коммита:
`docker compose build backend && docker compose up -d backend`.
Новые apt-зависимости: libpango/libcairo/libgdk-pixbuf для WeasyPrint.

### 6.5 deploy note
Добавлены `docker-compose.prod.yml`, `nginx/nginx.prod.conf`,
`nginx/templates/default.conf.template`, `scripts/init-letsencrypt.sh`.
Первый запуск в проде — следовать разделам ниже.

---

## 1. Требования

- VPS с Ubuntu 22.04+ (или совместимый Linux)
- Docker 24+, Docker Compose v2 (`docker compose`, не `docker-compose`)
- Открытые порты `80` и `443` (HTTP/HTTPS)
- Домен с DNS A-записью на IP VPS — должен резолвиться **до** запуска certbot
- Минимум 2 GB RAM, 20 GB диска

## 2. Подготовка VPS

```bash
# Установка Docker (официальный скрипт)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Клон репозитория
git clone https://github.com/yourname/weather-agro.git
cd weather-agro

# Каталог для логов nginx (монтируется в контейнер)
mkdir -p logs/nginx
```

## 3. `.env`

```bash
cp .env.example .env
nano .env
```

Минимум для prod заполнить:
- `POSTGRES_PASSWORD` — сильный пароль (не дефолтный)
- `SECRET_KEY` — `openssl rand -hex 32`
- `ENCRYPTION_KEY` — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- `DOMAIN=your-domain.com`
- `LETSENCRYPT_EMAIL=you@example.com`
- `FRONTEND_URL=https://your-domain.com`
- `CORS_ORIGINS=https://your-domain.com`
- `VITE_API_URL=https://your-domain.com/api`
- `OPENWEATHERMAP_API_KEY`, `TELEGRAM_BOT_TOKEN`, Yandex.Disk — по необходимости

## 4. Сборка образов

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```

## 5. Выпуск SSL-сертификата (первый запуск)

DNS должен уже указывать на VPS!

Сначала — тест в staging-окружении Let's Encrypt (не упирается в rate-limit):
```bash
export DOMAIN=your-domain.com
export LETSENCRYPT_EMAIL=you@example.com

STAGING=1 ./scripts/init-letsencrypt.sh
```

Если всё прошло, удалить staging-сертификат и выпустить настоящий:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker volume rm weather-agro_letsencrypt
./scripts/init-letsencrypt.sh
```

## 6. Запуск стека

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Проверка состояния:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Все сервисы должны быть `healthy` через ~30 секунд:
`db`, `backend`, `frontend`, `nginx`, `telegram_bot`, `certbot`.

## 7. Миграции и сиды

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.scripts.seed
```

## 8. Проверка работоспособности

```bash
# HTTP должен редиректить на HTTPS
curl -I http://your-domain.com
# HTTP/1.1 301 Moved Permanently
# Location: https://your-domain.com/

# HTTPS отвечает
curl -I https://your-domain.com
# HTTP/2 200

# Swagger
curl https://your-domain.com/api/docs

# Healthcheck бекенда через nginx
curl https://your-domain.com/api/health

# SSL Labs (после прогрева ~5 мин):
# https://www.ssllabs.com/ssltest/analyze.html?d=your-domain.com
# Ожидаемая оценка: A или A+ (с включённым HSTS).
```

## 9. Автообновление сертификата

Контейнер `certbot` запускает `certbot renew` каждые **12 часов**. Сертификат
обновляется автоматически за 30 дней до истечения. Nginx раз в 6 часов делает
`reload`, чтобы подхватить свежие файлы — внешнего cron не требуется.

Принудительно обновить руками:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm \
  certbot renew --webroot --webroot-path=/var/www/certbot --force-renewal
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
```

## 10. Логи

JSON-логи nginx — на хосте в `./logs/nginx/`:
```bash
tail -f logs/nginx/access.log | jq .
tail -f logs/nginx/error.log
```

Логи остальных сервисов:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f telegram_bot
```

## 11. Обновление приложения

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
```

(Полноценный `scripts/deploy.sh` появится в задаче 6.6.)

## 12. Тонкости и safety

- **Секреты только в `.env`** — он в `.gitignore`. Не коммитить.
- **Volume `letsencrypt`** содержит приватный ключ — не выкладывать наружу.
- **HSTS** включён на 2 года (`max-age=63072000`) — после первого успешного
  захода браузер не пустит на HTTP-версию. Перед сменой домена/откатом на
  HTTP — снимите HSTS заранее.
- **Бэкап:** содержимое volume `letsencrypt` можно потерять — certbot
  выпустит заново, но Let's Encrypt имеет лимит 5 дубликатов в неделю.
- **Frontend uploads:** /uploads/ отдаёт сам nginx из shared volume (без
  проксирования в backend) — нагрузки на FastAPI на статике нет.
