# 🌾 Weather Agro — Система мониторинга погоды для агрохозяйства

Веб-приложение для сбора, хранения, анализа и визуализации погодных данных по локациям выращивания и закупки овощных культур.

## 🎯 Возможности

- 📡 **Автоматический сбор погоды** с Open-Meteo, NASA POWER, OpenWeatherMap
- 📊 **10+ лет истории** для каждой локации
- 📈 **Графики и сравнения**: временные ряды, наложение по годам, heatmap, корреляции
- 🔬 **Аналитика**: климатические нормы, аномалии, статистика
- 🔔 **Алерты в Telegram**: жара, заморозки, ливни, любые кастомные условия
- 📔 **Журнал агрономических событий**: посадки, сборы, заметки с фото
- 📄 **PDF-отчёты** по сезону
- 💾 **Автобэкапы** на Яндекс.Диск
- 📱 **Адаптивный UI**: Apple HIG для дашборда, Notion-style для таблиц

## 🛠 Технологии

**Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 16 + TimescaleDB, APScheduler
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts, Plotly, TanStack Query, Zustand
**Инфраструктура:** Docker Compose, Nginx, Let's Encrypt
**Telegram:** python-telegram-bot

## 📋 Требования

- Docker 24+
- Docker Compose v2
- Минимум 2 GB RAM на VPS
- Домен с настроенным DNS (для production)

## 🚀 Быстрый старт (Development)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/yourname/weather-agro.git
cd weather-agro

# 2. Скопировать и заполнить .env
cp .env.example .env
nano .env  # заполнить хотя бы ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY

# 3. Запустить в dev-режиме (с hot-reload)
docker compose -f docker-compose.dev.yml up -d

# 4. Применить миграции и засидить данные
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# 5. Открыть в браузере
# Frontend: http://localhost:5173
# Backend Swagger: http://localhost:8000/api/docs
```

**Логин по умолчанию:** значения `ADMIN_USERNAME` / `ADMIN_PASSWORD` из `.env`

## 🌐 Production deploy

См. [`docs/DEPLOY.md`](docs/DEPLOY.md) — подробная инструкция по развёртыванию на VPS с HTTPS (Let's Encrypt).

Краткая версия:
```bash
# На VPS
git clone https://github.com/yourname/weather-agro.git
cd weather-agro
cp .env.example .env
nano .env  # заполнить production: DOMAIN, LETSENCRYPT_EMAIL, SECRET_KEY и т.д.

# Первый запуск — выпустить SSL-сертификат
DOMAIN=your-domain.com LETSENCRYPT_EMAIL=you@example.com \
  ./scripts/init-letsencrypt.sh

# Поднять весь стек
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  alembic upgrade head
```

Сертификат обновляется автоматически (`certbot renew` каждые 12ч). HTTP → HTTPS редирект, HSTS, JSON-логи nginx на `./logs/nginx/`, JSON-логи остальных сервисов — через docker `json-file` driver с ротацией (10MB × 5).

Обновление приложения:
```bash
./scripts/deploy.sh             # main
./scripts/deploy.sh release/v1  # ветка/тег
```

## 📁 Структура проекта

```
weather-agro/
├── backend/              # FastAPI приложение
│   ├── app/
│   │   ├── api/          # роутеры
│   │   ├── core/         # конфиг, безопасность
│   │   ├── db/           # модели, сессия
│   │   ├── services/     # бизнес-логика
│   │   ├── scheduler/    # фоновые задачи
│   │   └── telegram_bot/ # Telegram бот
│   └── alembic/          # миграции
├── frontend/             # React приложение
│   └── src/
│       ├── components/   # UI компоненты
│       ├── pages/        # страницы
│       ├── features/     # фичи по доменам
│       └── styles/       # темы Apple/Notion
├── nginx/                # конфигурация Nginx
├── docs/                 # документация
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── .env.example
├── PRD.md                # спецификация проекта
├── TASKS.md              # план разработки
└── README.md
```

## 📚 Документация

- [`PRD.md`](PRD.md) — полная спецификация проекта
- [`TASKS.md`](TASKS.md) — детальный план разработки
- [`CLAUDE_PROMPT.md`](CLAUDE_PROMPT.md) — шаблон промпта для Claude Code
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — инструкция по деплою (создаётся в этапе 6.7)
- [`docs/BACKUP.md`](docs/BACKUP.md) — настройка бэкапов
- [`docs/TELEGRAM.md`](docs/TELEGRAM.md) — настройка Telegram-бота
- [`docs/API.md`](docs/API.md) — описание API (+ Swagger на `/api/docs`)

## 🧪 Тесты

```bash
# Backend
docker compose exec backend pytest

# С покрытием
docker compose exec backend pytest --cov=app --cov-report=html
```

## 🗄 Бэкапы

Автоматический бэкап БД на Яндекс.Диск настраивается в разделе «Настройки» приложения.
Восстановление:
```bash
docker compose exec backend python -m app.scripts.restore <backup_file>
```

См. [`docs/BACKUP.md`](docs/BACKUP.md).

## 🔧 Полезные команды

```bash
# Логи
docker compose logs -f backend
docker compose logs -f telegram_bot

# Создать миграцию
docker compose exec backend alembic revision --autogenerate -m "description"

# Применить миграции
docker compose exec backend alembic upgrade head

# Откатить миграцию
docker compose exec backend alembic downgrade -1

# Войти в БД
docker compose exec db psql -U weather -d weather

# Пересобрать контейнер
docker compose up -d --build backend
```

## 🛣 Roadmap

- [x] Этап 0–6: MVP (сбор данных, графики, алерты, журнал, отчёты, деплой)
- [ ] Этап 7: визуальная стилизация Apple HIG / Notion
- [ ] Этап 8: ML — прогноз урожая на основе истории погоды и журнала

## 📝 Лицензия

Личный проект. Все права защищены.

## 👤 Автор

Личное использование для управления агрохозяйством.