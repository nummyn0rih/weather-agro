# TASKS: План задач разработки

> Каждая задача помечена тегом слоя:
>
> - 🔧 **BE** — Backend / Логика
> - ⚙️ **FE-F** — Frontend / Функциональный
> - 🎨 **FE-V** — Frontend / Визуальный
> - 🚀 **INFRA** — Инфраструктура / DevOps
>
> Зависимости указаны как `→ #номер`.

---

## Этап 0: Инициализация проекта

### 0.1 🚀 INFRA — Инициализация репозитория

**Описание:** Создать структуру проекта согласно PRD.md раздел 12.
**DoD:**

- [x] Создана структура папок `backend/`, `frontend/`, `nginx/`
- [x] Создан `.gitignore` (Python, Node, IDE, .env)
- [x] Создан `README.md` с базовым описанием
- [x] Создан `.env.example` со всеми переменными
- [x] `git init` и первый коммит

### 0.2 🚀 INFRA — Базовый Docker Compose

**Описание:** Настроить `docker-compose.yml` со всеми сервисами.
**DoD:**

- [x] Сервисы: `db` (TimescaleDB), `backend`, `frontend`, `nginx`, `telegram_bot`
- [x] Volumes для данных PostgreSQL и uploads
- [x] Внутренняя сеть
- [x] `docker-compose.dev.yml` с hot-reload для backend и frontend
- [ ] `docker compose up` поднимает всё без ошибок (требует установки Docker — не верифицировано)

---

## Этап 1: Фундамент (Backend)

### 1.1 🔧 BE — Инициализация FastAPI приложения

**Описание:** Базовый каркас FastAPI с роутингом и конфигом.
**DoD:**

- [x] `pyproject.toml` с зависимостями (fastapi, sqlalchemy, alembic, pydantic, httpx, apscheduler, python-jose, bcrypt, asyncpg)
- [x] Структура `app/` согласно PRD
- [x] `app/main.py` с CORS, health-check `GET /api/health`
- [x] `app/core/config.py` (Pydantic Settings, чтение `.env`)
- [x] Логирование (structlog или logging)
- [x] Swagger доступен на `/api/docs`

### 1.2 🔧 BE — Подключение БД и миграции

**Описание:** SQLAlchemy 2.0 + Alembic + TimescaleDB.
**DoD:**

- [x] `app/db/session.py` (async engine, session factory)
- [x] Базовая модель в `app/db/base.py`
- [x] Alembic настроен (`alembic init`)
- [x] Первая миграция: создание расширения TimescaleDB
- [x] Healthcheck эндпоинт проверяет соединение с БД

### 1.3 🔧 BE — Модели БД (все таблицы)

**Описание:** Создать все модели согласно PRD раздел 6.
**DoD:**

- [x] Модели: `User`, `Location`, `Crop`, `LocationCrop`, `WeatherDaily`, `WeatherForecast`, `FieldEvent`, `AlertRule`, `AlertHistory`, `Setting`
- [x] Миграция создаёт все таблицы
- [x] `weather_daily` и `weather_forecast` — hypertables (через `SELECT create_hypertable`)
- [x] Сидер для справочника `crops` с базовыми температурами

### 1.4 🔧 BE — Аутентификация JWT

**Описание:** Логин, refresh, защита эндпоинтов.
**Зависит от:** → 1.3
**DoD:**

- [x] `POST /api/auth/login` (возвращает access + refresh токены)
- [x] `POST /api/auth/refresh`
- [x] `POST /api/auth/logout`
- [x] Dependency `get_current_user`
- [x] Bcrypt для хеширования
- [x] Rate limiting на login (slowapi)
- [x] Тест: успешный логин, неверный пароль, refresh
- [x] Сидер: создаёт admin-пользователя из `ADMIN_USERNAME`/`ADMIN_PASSWORD`

### 1.5 🔧 BE — CRUD локаций

**Описание:** API для управления локациями.
**Зависит от:** → 1.4
**DoD:**

- [x] `GET /api/locations` — список с фильтрами (region, type)
- [x] `POST /api/locations` — создать
- [x] `GET /api/locations/{id}` — детали
- [x] `PUT /api/locations/{id}` — обновить
- [x] `DELETE /api/locations/{id}`
- [x] Pydantic-схемы (LocationCreate, LocationUpdate, LocationResponse)
- [x] Тесты для всех эндпоинтов

### 1.6 🔧 BE — Клиент Open-Meteo

**Описание:** Сервис для получения данных с Open-Meteo Archive API и Forecast API.
**DoD:**

- [x] `app/services/weather/open_meteo.py`
- [x] Метод `fetch_historical(lat, lon, date_from, date_to) -> List[WeatherDailyDTO]`
- [x] Метод `fetch_forecast(lat, lon, days=16) -> List[WeatherDailyDTO]`
- [x] Маппинг полей API → модель БД
- [x] Расчёт VPD из T и RH в этом же сервисе
- [x] Retry с экспоненциальной задержкой (tenacity)
- [x] Тест с замоканным httpx

### 1.7 🔧 BE — Клиент NASA POWER

**Описание:** Сервис для NASA POWER API (исторические данные).
**DoD:**

- [x] `app/services/weather/nasa_power.py`
- [x] Метод `fetch_historical(lat, lon, date_from, date_to)`
- [x] Маппинг полей (учесть отсутствие некоторых параметров)
- [x] Retry
- [x] Тест с замоканным ответом

### 1.8 🔧 BE — Сервис расчётов (GDD, VPD, frost_hours)

**Описание:** Чистые функции для производных параметров.
**DoD:**

- [x] `app/services/analytics/calculators.py`
- [x] `calculate_vpd(temp_c, humidity_pct) -> float`
- [x] `calculate_gdd(temp_min, temp_max, base_temp) -> float`
- [x] `calculate_frost_hours(hourly_temps) -> int`
- [x] Unit-тесты с известными значениями

### 1.9 🔧 BE — Загрузка истории при добавлении локации ✅

**Описание:** Background task на 10 лет назад.
**Зависит от:** → 1.5, 1.6, 1.7
**DoD:**

- [x] При `POST /api/locations` запускается background task (FastAPI BackgroundTasks)
- [x] Загрузка чанками по 1 году (чтобы не упереться в лимиты API)
- [x] Сохранение прогресса в `Location.import_status` (`pending` / `in_progress` / `done` / `error`)
- [x] `Location.import_progress` (0–100)
- [x] `GET /api/locations/{id}/import-status`
- [x] Идемпотентность: повторный запуск не дублирует данные (UPSERT)

### 1.10 🔧 BE — Эндпоинт получения погодных данных ✅

**Описание:** Универсальный эндпоинт для запроса данных.
**Зависит от:** → 1.9
**DoD:**

- [x] `GET /api/weather/daily` с параметрами:
  - `location_ids: List[int]`
  - `parameters: List[str]` (temp_avg, precipitation, ...)
  - `date_from: date`, `date_to: date`
  - `source: str` (`open_meteo` / `nasa_power` / `average`)
  - `aggregation: str` (`day` / `week` / `month` / `season` / `year`)
- [x] Возвращает массив точек `{time, location_id, ...values}`
- [x] При `source=average` — среднее по доступным источникам
- [x] Тест на корректность агрегации

### 1.11 🔧 BE — Планировщик APScheduler ✅

**Описание:** Фоновые задачи по расписанию.
**Зависит от:** → 1.9
**DoD:**

- [x] `app/scheduler/jobs.py`
- [x] Задача: ежедневная загрузка вчерашних данных (03:00 МСК)
- [x] Задача: обновление прогноза (06:00 и 18:00 МСК)
- [x] Логирование выполнения в БД (таблица `scheduler_logs`)
- [x] Запуск на старте приложения

---

## Этап 2: Frontend-каркас

### 2.1 ⚙️ FE-F — Инициализация Vite + React + TS

**Описание:** Базовый каркас фронтенда.
**DoD:**

- [x] `pnpm create vite` с шаблоном React+TS
- [x] Tailwind CSS установлен и настроен
- [x] shadcn/ui инициализирован (`npx shadcn-ui init`)
- [x] ESLint + Prettier настроены
- [x] `tsconfig.json` строгий режим
- [x] Алиасы путей (`@/components`, `@/lib`)

### 2.2 ⚙️ FE-F — API-клиент и TanStack Query

**Описание:** Базовый клиент для запросов к backend.
**Зависит от:** → 2.1
**DoD:**

- [x] `src/lib/api.ts` — axios или fetch wrapper
- [x] Перехват 401 → redirect на `/login`
- [x] Автоматическое добавление JWT в заголовки
- [x] Refresh-токен механика (auto-retry на 401)
- [x] TanStack Query Provider в `App.tsx`

### 2.3 ⚙️ FE-F — Аутентификация (страница логина)

**Описание:** Форма входа, хранение токенов.
**Зависит от:** → 2.2, 1.4
**DoD:**

- [x] Страница `/login` с формой (логин, пароль)
- [x] Хранение токенов в localStorage
- [x] Zustand store `useAuthStore`
- [x] ProtectedRoute компонент
- [x] Logout-кнопка в layout

### 2.4 ⚙️ FE-F — Layout и роутинг ✅

**Описание:** Главный каркас приложения.
**Зависит от:** → 2.3
**DoD:**

- [x] `Layout.tsx` с sidebar (навигация) и header
- [x] Роуты: `/`, `/charts`, `/tables`, `/analytics`, `/events`, `/locations`, `/alerts`, `/reports`, `/settings`
- [x] Активный пункт меню подсвечивается
- [x] Mobile: sidebar становится drawer
- [x] Toggle светлой/тёмной темы (next-themes или собственная реализация)

### 2.5 ⚙️ FE-F — Страница «Локации» (список + CRUD) ✅

**Описание:** Управление локациями.
**Зависит от:** → 2.4, 1.5
**DoD:**

- [x] Таблица локаций (shadcn/ui Table)
- [x] Кнопка «Добавить локацию» → модальное окно с формой
- [x] Поля формы: название, координаты, регион, тип, культуры _(культуры отложены до появления BE-эндпоинта `location_crops`)_
- [x] Редактирование (клик по строке)
- [x] Удаление с подтверждением
- [x] Отображение прогресса загрузки истории (polling каждые 5 сек)

### 2.6 ⚙️ FE-F — Дашборд (функциональная версия) ✅

**Описание:** Главная страница с базовыми карточками.
**Зависит от:** → 2.4, 1.10
**DoD:**

- [x] Сетка карточек локаций
- [x] На каждой карточке: название, текущая T, осадки за сегодня, мини-график за 7 дней
- [x] Блок «Активные алерты» (заглушка пока, до этапа 4)
- [x] Блок «Прогноз 7 дней» (выбранная локация)
- [x] Loading skeletons для всех блоков

---

## Этап 3: Анализ данных

### 3.1 🔧 BE — API для timeseries графиков

**Описание:** Расширение эндпоинта `/api/weather/daily` для нужд графиков.
**Зависит от:** → 1.10
**DoD:**

- [x] Поддержка multi-location, multi-parameter
- [x] Опция `compare_years: List[int]` — возвращает данные с overlay по годам
- [x] Эндпоинт `GET /api/weather/heatmap` — данные для тепловой карты
- [x] Эндпоинт `GET /api/weather/cumulative` — накопительные суммы (осадки, GDD)

### 3.2 🔧 BE — API для статистики и таблиц

**Описание:** Агрегации для табличного представления.
**DoD:**

- [x] `GET /api/weather/stats` — мин/макс/среднее/сумма по группировке
- [x] Поддержка фильтров (locations, parameters, date range, aggregation level)
- [x] Экспорт CSV: `GET /api/weather/export?format=csv`
- [x] Экспорт Excel: `format=xlsx` (openpyxl)

### 3.3 🔧 BE — Climate normals

**Описание:** Расчёт многолетних норм.
**DoD:**

- [x] Сервис `app/services/analytics/climate_normals.py`
- [x] `calculate_normals(location_id, parameter, period='month')` → mean, std, min, max за все доступные годы
- [x] Кэширование результатов в таблице `climate_normals`
- [x] Cron-задача обновления раз в месяц
- [x] `GET /api/analytics/normals?location_id=X&parameter=Y`

### 3.4 🔧 BE — Аномалии

**Описание:** Отклонения от климатической нормы.
**Зависит от:** → 3.3
**DoD:**

- [x] `GET /api/analytics/anomalies` — данные с пометкой степени отклонения (none / >1σ / >2σ)
- [x] Параметры: location_id, parameter, date_from, date_to

### 3.5 🔧 BE — Корреляции

**Описание:** Расчёт матрицы корреляций Пирсона.
**DoD:**

- [x] `GET /api/analytics/correlations` — параметры: location_id, parameters[], date_from, date_to
- [x] Возвращает матрицу NxN с коэффициентами
- [x] Использовать numpy/pandas для расчёта

### 3.6 ⚙️ FE-F — Страница «Графики»

**Описание:** Интерактивные графики на Recharts.
**Зависит от:** → 3.1, 2.4
**DoD:**

- [x] Форма выбора: локации (multi-select), параметры (multi-select), период (presets + date picker), источник
- [x] Тип графика: временной ряд, сравнение локаций, overlay по годам, накопительный
- [x] Кнопка «Heatmap» (Plotly)
- [x] Кнопка «Корреляции» (матрица через Plotly heatmap)
- [x] Экспорт PNG/SVG/CSV
- [x] URL-state (фильтры в query params, можно поделиться ссылкой)

### 3.7 ⚙️ FE-F — Страница «Таблицы»

**Описание:** Гибкая таблица с агрегациями.
**Зависит от:** → 3.2, 2.4
**DoD:**

- [x] Форма выбора (как в графиках) + группировка
- [x] Data table с сортировкой, фильтрацией
- [x] Условное форматирование (цвет ячейки по значению)
- [x] Экспорт CSV/Excel
- [x] Сохранение пресетов (localStorage)

### 3.8 ⚙️ FE-F — Страница «Аналитика»

**Описание:** Сводка, аномалии, корреляции, climate normals.
**Зависит от:** → 3.3, 3.4, 3.5, 2.4
**DoD:**

- [x] Вкладка «Статистика» — сводная таблица
- [x] Вкладка «Аномалии» — график с подсветкой отклонений
- [x] Вкладка «Корреляции» — heatmap
- [x] Вкладка «Climate normals» — графики норм по месяцам

---

## Этап 4: Алерты и Telegram

### 4.1 🔧 BE — CRUD правил алертов

**DoD:**

- [x] `GET/POST/PUT/DELETE /api/alerts/rules`
- [x] Pydantic-схемы AlertRule (parameter, condition, threshold, location_ids, enabled)
- [x] Тесты

### 4.2 🔧 BE — Движок алертов

**Описание:** Проверка правил по расписанию.
**Зависит от:** → 4.1, 1.11
**DoD:**

- [x] `app/services/alerts/engine.py`
- [x] Cron-задача: каждый час проверяет все enabled правила
- [x] При срабатывании — запись в `alert_history`
- [x] Дедупликация: не слать повторно одинаковый алерт в пределах N часов
- [x] Тесты с разными условиями

### 4.2.1 🔧 BE — Fix TZ: dedup сравнение в alerts engine ✅

**Описание:** В `app/services/alerts/engine.py:185` сравнение `last >= cutoff` падает с `TypeError: can't compare offset-naive and offset-aware datetimes` при прогоне на SQLite (aiosqlite драйвер возвращает naive datetime даже из колонки `TIMESTAMPTZ`). Postgres-prod не падает, но дефект скрытый — любой драйвер, теряющий tzinfo при чтении, сломает дедуп.

**Зависит от:** → 4.2

**DoD:**

- [x] `_last_triggered_at` в `engine.py` коэрсит naive → aware UTC перед возвратом
- [x] Grep по `backend/app/services/alerts/` — все `datetime.now()` используют `tz=UTC`
- [x] `tests/test_alert_engine.py::test_dedup_blocks_repeat_within_window` зелёный
- [x] `tests/test_alert_engine.py::test_dedup_allows_repeat_after_window` зелёный
- [x] Регрессии нет: полный прогон pytest без новых fail

### 4.3 🔧 BE — Telegram-бот (каркас)

**Описание:** Базовый бот с командами.
**DoD:**

- [x] `app/telegram_bot/main.py`
- [x] Запускается как отдельный процесс (Docker service)
- [x] Команды: `/start`, `/help`, `/locations`, `/weather <id>`, `/forecast <id>`, `/alerts`, `/alerts_history`, `/stats <id> <period>`
- [x] Привязка chat_id через одноразовый код (генерируется в UI)
- [x] Доступ только для привязанного chat_id

### 4.4 🔧 BE — Интеграция алертов с Telegram ✅

**Зависит от:** → 4.2, 4.3
**DoD:**

- [x] При срабатывании алерта — отправка сообщения в Telegram
- [x] Формат: эмодзи + локация + параметр + значение + время
- [x] Обработка ошибок отправки (retry 3 раза)

### 4.4.0 🔧 BE — AlertHistory: snapshot-поля и nullable FK ✅

**Зависит от:** → 4.1, 4.2

**Контекст:**
Текущая `AlertHistory` хранит только `id, rule_id, location_id, triggered_at, value, message`. Для исторической корректности (правило могут изменить/удалить) нужен snapshot полей правила на момент срабатывания. Также FK на `alert_rules` и `locations` сейчас `ON DELETE CASCADE` — история теряется при удалении правила/локации; меняем на `SET NULL`.

**Стратегия миграции — two-step в одном файле:**

1. add new columns nullable=True
2. backfill из `alert_rules` JOIN по `rule_id` (для записей с существующим правилом)
3. backfill placeholder'ами для orphan-записей (`(deleted rule)`, `unknown`, `gt`, `0`)
4. `ALTER COLUMN ... SET NOT NULL` на 4 поля (`threshold_max_snapshot` остаётся nullable)
5. drop+recreate FK `alert_history_rule_id_fkey`, `alert_history_location_id_fkey` с `ON DELETE SET NULL`, сделать `rule_id` и `location_id` nullable

**DoD:**

- [x] Миграция Alembic two-step в одном файле (add nullable → backfill → SET NOT NULL)
- [x] Колонки добавлены: `rule_name_snapshot String(200) NOT NULL`, `parameter_snapshot String(50) NOT NULL`, `condition_snapshot String(10) NOT NULL`, `threshold_snapshot Float NOT NULL`, `threshold_max_snapshot Float NULL`
- [x] FK `alert_history_rule_id_fkey` → `ON DELETE SET NULL`, `rule_id` nullable
- [x] FK `alert_history_location_id_fkey` → `ON DELETE SET NULL`, `location_id` nullable
- [x] SQLAlchemy модель `AlertHistory` синхронизирована (5 snapshot полей + nullable FK)
- [x] `app/services/alerts/engine.py:193-199` обновлён: создание `AlertHistory` заполняет 5 snapshot полей из `rule.*`
- [x] Существующие тесты alert engine проходят (адаптировать assertions)
- [x] Новый тест: после срабатывания все snapshot поля совпадают с rule на момент создания; изменение rule после срабатывания не меняет snapshot
- [x] Тест: удаление `AlertRule` оставляет связанную запись `AlertHistory` (не каскад), `rule_id` становится `NULL`, snapshot-поля сохранены
- [x] Тест: удаление `Location` оставляет связанную запись `AlertHistory`, `location_id` становится `NULL`
- [x] `alembic upgrade head` чисто на свежей БД
- [x] `alembic downgrade -1` чисто
- [x] `alembic upgrade head` после downgrade чисто
- [x] Smoke на непустой БД: создать `AlertHistory` pre-migration → upgrade → snapshot заполнен корректно

### 4.4.1 🔧 BE — История срабатываний алертов (API) ✅

**Зависит от:** → 4.1, 4.2, 4.4.0

**DoD:**

- [x] `GET /api/alerts/history` зарегистрирован, виден в Swagger
- [x] Фильтры query: `location_id`, `rule_id`, `date_from`, `date_to`
- [x] Пагинация: `limit` (default 50, max 200), `offset` (default 0)
- [x] Сортировка по `triggered_at DESC`
- [x] Response: `{ items: AlertHistoryItem[], total: int, limit: int, offset: int }`
- [x] `AlertHistoryItem` поля: `id, rule_id (nullable), rule_name (snapshot), location_id (nullable), location_name, parameter (snapshot), condition (snapshot), threshold (snapshot), threshold_max (snapshot, nullable), value, triggered_at, message`
- [x] `location_name` из связанной `Location.name`; если `location_id IS NULL` → `'(удалена)'`
- [x] `rule_name` берётся из `rule_name_snapshot` (всегда есть, даже если `rule_id IS NULL`)
- [x] Eager loading `Location` через `selectinload` (rule не подгружаем — все нужные данные в snapshot-полях)
- [x] Pydantic v2 схемы (`AlertHistoryItem`, `AlertHistoryResponse`)
- [x] Auth: `Depends(get_current_user)`
- [x] Тесты pytest:
  - [x] фильтр по `location_id`, `rule_id`
  - [x] фильтр по `date_from`/`date_to`
  - [x] пагинация (limit=2 offset=0 → 2; offset=2 → остальные)
  - [x] пустой результат
  - [x] запись с `rule_id=NULL` (rule удалено) — корректно отдаётся, `rule_name` = snapshot
  - [x] запись с `location_id=NULL` — `location_name='(удалена)'`
- [x] Создан `docs/DECISIONS.md` с ADR: `/api/...` без `/v1/` (MVP, миграция через nginx rewrite/новый prefix при необходимости)

### 4.5 ⚙️ FE-F — Страница «Алерты»

**Зависит от:** → 4.1, 4.4.1, 2.4
**DoD:**

- [x] Список правил с toggle включения
- [x] Форма создания/редактирования
- [x] Шаблоны: «Жара», «Заморозки», «Ливень»
- [x] Вкладка «История срабатываний» с фильтрами
- [x] Кнопка «Привязать Telegram» → модалка с кодом

---

## Этап 5: Журнал и отчёты

### 5.0.5 🔧 BE — Эндпоинт справочника культур ✅

**Описание:** GET-эндпоинт для списка культур (для FE-фильтров и форм).
**Зависит от:** → 1.4 (модель Crop, сидер)
**DoD:**

- [x] GET /api/crops → список { id, name, base_temperature, optimal_temp_min/max } из таблицы crops
- [x] Pydantic v2 схема CropResponse
- [x] Сортировка по name
- [x] Auth: требует Bearer token (как остальные /api/\*)
- [x] Тест happy path: GET → 200 + список из сидера
- [x] Тест 401 без токена

**Также:** проверить 2.5 — там crop-фильтр был отложен. После 5.0.5 → дополнить 2.5 (отдельным мелким PR или в рамках 5.4 если фильтр на той же странице).

### 5.1 🔧 BE — CRUD событий журнала ✅

**DoD:**

- [x] `GET/POST/PUT/DELETE /api/events`
- [x] Загрузка фото: `POST /api/events/{id}/photos` (multipart, до 5 файлов)
- [x] Сохранение в `/uploads/events/{event_id}/`
- [x] Удаление фото
- [x] Фильтры: location_id, event_type, crop_id, date range

### 5.2 🔧 BE — Привязка событий к погоде ✅

**Описание:** При получении события — отдавать погодные условия в этот день.
**Зависит от:** → 5.1, 1.10
**DoD:**

- [x] `GET /api/events/{id}` возвращает событие + объект `weather` (данные за `event_date` по `location_id`)
- [x] Если данных нет — поле `weather: null`
- [x] Тест на корректную привязку

### 5.3 🔧 BE — Генерация PDF-отчётов

**Описание:** Сезонный отчёт по локации в PDF.
**Зависит от:** → 5.1, 3.2, 3.4
**DoD:**

- [x] `app/services/reports/pdf_generator.py` (WeasyPrint)
- [x] HTML-шаблон отчёта (Jinja2): обложка, сводка погоды, графики (PNG), аномалии, события, урожайность
- [x] Графики рендерятся в PNG через matplotlib (на бэкенде)
- [x] `POST /api/reports/generate` с параметрами `location_id`, `season_year` → возвращает file_id
- [x] `GET /api/reports/{file_id}/download` → отдаёт PDF
- [x] Хранение сгенерированных отчётов в `/uploads/reports/`

### 5.3.1 🔧 BE — Удаление отчёта ✅

**Описание:** DELETE-эндпоинт для удаления сгенерированного PDF-отчёта (запись + файл).
**Зависит от:** → 5.3
**DoD:**

- [x] `DELETE /api/reports/{file_id}` — удаляет запись из БД и файл с диска (если существует)
- [x] 404 если запись не существует
- [x] Идемпотентность по файлу: отсутствие файла на диске не даёт 500 (логировать warning, БД-запись всё равно удалить)
- [x] Auth: `Depends(get_current_user)` (как остальные `/api/reports/*`)
- [x] Pydantic: response пустой / `204 No Content`
- [x] Тесты pytest:
  - [x] happy path: создать report со status=done + dummy-файл → DELETE → 204, файла нет, в БД нет
  - [x] 404 на несуществующий id
  - [x] 401 без токена
  - [x] файл отсутствует на диске → DELETE всё равно успешен, запись из БД удалена

### 5.4 ⚙️ FE-F — Страница «Журнал событий» ✅

**Зависит от:** → 5.1, 5.2, 2.4, 5.0.5
**DoD:**

- [x] Лента событий (карточки), сортировка по дате
- [x] Фильтры: локация, тип, культура, период (URL state: `?location=&type=&crop=&from=&to=`)
- [x] Кнопка «Добавить событие» → модалка с динамической формой:
  - Тип: «Посадка» / «Сбор» / «Заметка»
  - Поля меняются в зависимости от типа
  - Загрузка до 5 фото (drag-n-drop)
- [x] Просмотр события: данные + блок «Погода в этот день» + галерея фото
- [x] Редактирование, удаление с подтверждением

### 5.5 ⚙️ FE-F — Страница «Отчёты» ✅

**Зависит от:** → 5.3, 5.3.1, 2.4
**DoD:**

- [x] Форма: выбор локации, сезона
- [x] Кнопка «Сгенерировать» → запрос на backend, прогресс-индикатор
- [x] Список ранее сгенерированных отчётов с кнопками «Скачать», «Удалить»

---

## Этап 6: Прод-готовность

### 6.1 🔧 BE — Клиент OpenWeatherMap (опционально)

**DoD:**

- [x] `app/services/weather/openweathermap.py`
- [x] Метод `fetch_current(lat, lon)` — текущая погода
- [x] Метод `fetch_forecast(lat, lon)` — прогноз 5 дней
- [x] Учёт лимита бесплатного тарифа (60 req/min)
- [x] Активация только если в `.env` указан `OPENWEATHERMAP_API_KEY`
- [x] Тест с замоканным httpx

### 6.1.1 🔧 BE — Fix: TZ-aware агрегация в OpenWeatherMap forecast ✅

Зависит от: → 6.1
Блокирует: интеграцию OWM как источника alerts engine

DoD:

- [x] `fetch_forecast` группирует 3h-бакеты по локальной TZ локации
- [x] TZ берётся из `Location.timezone` (новое поле, NOT NULL, default `'UTC'`)
- [x] Решение зафиксировано в ADR-006 (`docs/DECISIONS.md`)
- [x] Тест: для локации UTC+3 заморозок в 02:00 локального попадает в правильный день
- [x] `fetch_current` тоже использует локальную TZ (симметрично с forecast)

### 6.2 🔧 BE — Бэкапы на Яндекс.Диск ✅

**Описание:** Автоматические бэкапы БД.
**DoD:**

- [x] `app/services/backup/yandex_disk.py` (WebDAV-клиент)
- [x] Скрипт `pg_dump` → gzip → upload на Яндекс.Диск
- [x] Cron-задача (04:00 МСК)
- [x] Ротация: 30 ежедневных + 12 ежемесячных
- [x] `POST /api/backup/run` — ручной запуск
- [x] `GET /api/backup/list` — список бэкапов на Яндекс.Диске
- [x] CLI-скрипт восстановления `app/scripts/restore.py` (`python -m app.scripts.restore`)
- [x] Логирование в БД (таблица `backup_logs`)

### 6.3.0 🔧 BE — Роли пользователей и активность

**Описание:** Добавление поля `is_admin` и `is_active` к модели `User`,
dependency `require_admin`, проверка `is_active` при логине и в
`get_current_user`. Базис для admin-эндпоинтов и инвайтов.

**Зависит от:** → 1.4 (auth уже реализован), → 1.3 (модели/миграции)

**DoD:**

- [x] Миграция Alembic: добавляет колонки в `users`
  - [x] `is_admin BOOLEAN NOT NULL DEFAULT FALSE`
  - [x] `is_active BOOLEAN NOT NULL DEFAULT TRUE`
  - [x] Backfill: `is_admin=true` для пользователя с
        `username == ${ADMIN_USERNAME}` (env)
  - [x] Все существующие пользователи получают `is_active=true`
- [x] Обновлена SQLAlchemy-модель `User` — добавлены оба поля
- [x] Сидер при создании admin устанавливает `is_admin=true`,
      `is_active=true`; при наличии существующего admin —
      проверяет/чинит флаги (idempotent)
- [x] Dependency `require_admin` в `app/api/deps.py`:
  - [x] Использует `get_current_user`
  - [x] Возвращает 403 если `is_admin=False`
  - [x] Возвращает 401 если пользователь неактивен (защита глубже)
- [x] `get_current_user` дополнительно проверяет `is_active=True`,
      иначе 401 с сообщением "User is inactive"
- [x] Login endpoint проверяет `is_active=True` перед выдачей токена,
      иначе 401 "User is inactive"
- [x] Тесты:
  - [x] `require_admin` пропускает admin
  - [x] `require_admin` возвращает 403 для обычного user
  - [x] `require_admin` возвращает 401 для неавторизованного запроса
  - [x] Логин неактивного пользователя → 401
  - [x] `get_current_user` с токеном неактивного юзера → 401
  - [x] Сидер на повторном запуске не дублирует и не сбрасывает флаги
- [x] Эндпоинт `GET /api/auth/me` возвращает поля `is_admin`,
      `is_active` (если эндпоинт уже есть — расширить ответ; если
      нет — создать в этой же задаче)

**Замечания:**

- Не защищаем существующие эндпоинты `require_admin` в этой задаче —
  это сделают задачи где данные эндпоинты создаются/уточняются
- Регистронезависимое сравнение username при логине — out of scope
  (опциональный backlog-пункт)

### 6.3.0.1 🔧 BE — Инвайт-система

**Описание:** Модель `Invite` и эндпоинты для создания/отзыва инвайтов
admin'ом и принятия инвайта новым пользователем.

**Зависит от:** → 6.3.0

**DoD:**

- [x] Миграция Alembic: таблица `invites`
  - [x] `id` PK
  - [x] `username VARCHAR(255) NOT NULL` (по соглашению — email)
  - [x] `is_admin BOOLEAN NOT NULL DEFAULT FALSE`
  - [x] `token VARCHAR(64) UNIQUE NOT NULL` (URL-safe random)
  - [x] `created_by_id` FK → users.id
  - [x] `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - [x] `expires_at TIMESTAMPTZ NOT NULL`
  - [x] `accepted_at TIMESTAMPTZ NULL`
  - [x] `revoked_at TIMESTAMPTZ NULL`
  - [x] Индекс по `token`
- [x] SQLAlchemy-модель `Invite`
- [x] Pydantic-схемы:
  - [x] `InviteCreate { username: EmailStr, is_admin: bool = False }`
  - [x] `InviteRead` (без token при list)
  - [x] `InviteAccept { password: str (min 8) }`
- [x] Сервис `app/services/invites.py`:
  - [x] `create_invite(session, username, is_admin, created_by)` —
        генерит token (`secrets.token_urlsafe(32)`),
        `expires_at = now() + 7 days`. Если username уже занят
        активным юзером — 409. Если уже есть активный неиспользованный
        инвайт на этот username — 409 (можно сначала revoke).
  - [x] `revoke_invite(session, invite_id)` — ставит `revoked_at`
  - [x] `get_invite_by_token(session, token)` — валидирует:
        не accepted, не revoked, не expired
  - [x] `accept_invite(session, token, password)` — создаёт User
        (`is_admin` из инвайта, `is_active=True`, bcrypt-хеш),
        ставит `accepted_at`, возвращает User
- [x] Эндпоинты:
  - [x] `POST /api/admin/invites` — `require_admin`,
        body `InviteCreate`, ответ `{id, token, invite_url}`,
        `invite_url` собирается из `FRONTEND_URL` env +
        `/accept-invite?token=...`
  - [x] `GET /api/admin/invites` — `require_admin`, список всех
        инвайтов со статусами (pending/accepted/revoked/expired)
  - [x] `DELETE /api/admin/invites/{id}` — `require_admin`,
        revoke. 404 если уже accepted.
  - [x] `GET /api/auth/invites/{token}` — публичный, валидирует
        токен, возвращает `{username, is_admin}` для отображения на
        форме accept-invite. 404/410 при невалидном токене.
  - [x] `POST /api/auth/invites/{token}/accept` — публичный,
        body `InviteAccept`, создаёт User, возвращает access+refresh
        токены (auto-login)
- [x] Rate limiting через slowapi на публичных эндпоинтах
      `/api/auth/invites/*`
- [x] Тесты:
  - [x] Admin создаёт инвайт → 201 с token и invite_url
  - [x] Не-admin создаёт инвайт → 403
  - [x] Создание инвайта на существующий username → 409
  - [x] GET по валидному токену → 200 с username/is_admin
  - [x] GET по revoked токену → 410
  - [x] GET по expired токену → 410
  - [x] GET по accepted токену → 410
  - [x] Accept валидного инвайта → 200, юзер создан, токены выданы
  - [x] Accept того же токена дважды → второй раз 410
  - [x] Revoke инвайта → 204; последующий GET → 410
  - [x] Revoke accepted инвайта → 404
  - [x] List возвращает все статусы корректно

**Замечания:**

- `FRONTEND_URL` добавить в `.env.example`
- Поле `username` в `InviteCreate` валидируется как `EmailStr`
- Вычисление статуса "expired" — на лету при чтении, не cron

## 6.3.0-FE.1 — Foundation: auth store + AdminRoute + UI deps

**Статус:** ✅ done

**Цель:** Подготовить инфраструктуру под admin-страницы. Без новых страниц.

**Скоуп:**

- Установить deps: react-hook-form, zod, @hookform/resolvers, sonner
- Добавить shadcn: form, sonner, checkbox, switch, dropdown-menu, badge, tooltip
- Расширить `stores/auth.ts`: userId, isAdmin, isActive, bootstrapping; методы setSession (с fetch /auth/me), refreshUserInfo, bootstrap, clearSession
- ProtectedRoute учитывает bootstrapping (лоадер вместо мгновенного редиректа)
- Создать `components/AdminRoute.tsx`
- Подключить `<Toaster />` в App.tsx
- Bootstrap-вызов на старте App

**Acceptance:**

- `npm run build` — 0 ошибок
- Login админом → стор: `isAdmin=true`
- Login обычным → `isAdmin=false`
- F5 на защищённой странице → лоадер, затем страница (не редирект на login)
- `/auth/me` вызывается один раз после login и один раз на bootstrap
- `is_active=false` от /auth/me → автоматический logout

---

## 6.3.0-FE.2 — Accept Invite page

**Статус:** ✅ выполнено

**Цель:** Публичная страница `/accept-invite/:token` для регистрации по инвайту.

**Скоуп:**

- `pages/AcceptInvitePage.tsx` — без auth-guard
- На mount: `GET /auth/invites/{token}` → показать email/имя или ошибку (invalid/expired/used)
- Форма (rhf+zod): username (3-50, [a-zA-Z0-9_]+), password (≥8), passwordConfirm (refine match)
- Submit: `POST /auth/accept-invite` с {token, username, password}
- Успех → toast "Аккаунт создан, войдите в систему" → navigate `/login`
- Роут в `App.tsx`

**Acceptance:**

- Валидный токен → форма видна, инфа об инвайте отображается
- Невалидный/истёкший/использованный → экран ошибки
- Submit с валидными данными → успех + редирект
- Backend errors → inline или toast

---

## 6.3.0-FE.3 — Admin Users page

**Статус:** ✅ done

**Цель:** `/admin/users` — управление пользователями.

**Скоуп:**

- `pages/admin/UsersPage.tsx` под AdminRoute
- TanStack Query: список `GET /admin/users`
- Таблица (shadcn): id, username, email, is_admin (Badge), is_active (Badge), created_at, actions
- Actions (dropdown-menu):
  - Сделать/снять админа → `PATCH /admin/users/{id}` с {is_admin}
  - Активировать/деактивировать → `PATCH /admin/users/{id}` с {is_active} (AlertDialog для деактивации)
  - Сбросить пароль → диалог с input + кнопка "Сгенерировать" (16 символов crypto.getRandomValues) + "Скопировать" + предупреждение "Сохраните пароль до отправки" → `POST /admin/users/{id}/reset-password` с {password}
- Self-lockout 4xx → sonner error toast
- Mutations + invalidateQueries
- Роут `/admin/users` в App.tsx
- Ссылка в header/menu только если isAdmin

**Acceptance:**

- Таблица грузится, badges корректны
- Все три actions работают, инвалидация списка
- Reset-password диалог: генератор, copy, валидация ≥8
- Деактивация себя → backend error → toast

---

## 6.3.0-FE.4 — Admin Invites page

**Статус:** ✅ done

**Цель:** `/admin/invites` — создание и отзыв инвайтов.

**Скоуп (фактический):**

- Расширена существующая `pages/admin/InvitesPage.tsx` (read-only список из FE.read-only) под AdminRoute
- Кнопка "Создать инвайт" в шапке → двухстадийный диалог (rhf+zod):
  - Стадия 1: email (EmailStr-валидация), is_admin (Switch) → `POST /admin/invites` (схема `InviteCreate { username, is_admin }` — backend не принимает `expires_in_days` / `name`, TTL зашит 7 дней)
  - Стадия 2: показ ссылки `${origin}/accept-invite/${token}` (path param, не query) с кнопкой Copy и предупреждением "показывается один раз"
- Action "Отозвать" (Trash2) в строках со status='pending' → AlertDialog → `DELETE /admin/invites/{id}` (soft revoke: row остаётся, status переходит в 'revoked')
- TanStack Query + `invalidateQueries(['admin','invites'])`
- Роут `/admin/invites` уже зарегистрирован в App.tsx (FE.read-only); ссылка в header — admin-only через `isAdmin`
- Доп: Self-lockout guards в UsersPage (FE.3 тех.долг закрыт): "Снять админа" disabled когда `user.is_admin && user.id === currentUserId`; "Деактивировать" disabled для self

**Acceptance:**

- Создание инвайта показывает копируемую ссылку
- Список обновляется после create/revoke
- Revoke с подтверждением

### 6.3.0.2 🔧 BE — Admin-эндпоинты управления пользователями

**Описание:** Список пользователей, сброс пароля, деактивация/
активация, изменение роли.

**Зависит от:** → 6.3.0.1

**DoD:**

- [x] Pydantic-схемы:
  - [x] `UserRead { id, username, is_admin, is_active, created_at }`
  - [x] `UserPasswordReset { password: str (min 8) }`
  - [x] `UserUpdate { is_admin?: bool, is_active?: bool }`
- [x] Эндпоинты (все `require_admin`):
  - [x] `GET /api/admin/users` — список всех пользователей
  - [x] `GET /api/admin/users/{id}` — один пользователь
  - [x] `PATCH /api/admin/users/{id}` — обновление is_admin/is_active
  - [x] `POST /api/admin/users/{id}/reset-password` —
        body `UserPasswordReset`, обновляет хеш пароля
- [x] Защита от self-lockout:
  - [x] Admin не может снять `is_admin` с самого себя → 400
  - [x] Admin не может деактивировать самого себя → 400
  - [x] Нельзя удалить/деактивировать последнего активного admin'a
        → 400 с понятным сообщением
- [x] Тесты:
  - [x] Admin видит список юзеров
  - [x] Не-admin → 403
  - [x] Сброс пароля работает (старый не подходит, новый подходит)
  - [x] Деактивация юзера → юзер не может залогиниться
  - [x] Реактивация → может
  - [x] Self-demote → 400
  - [x] Self-deactivate → 400
  - [x] Деактивация последнего admin'a → 400
  - [x] Снятие is_admin с последнего admin'a → 400

**Замечания:**

- Удаление пользователя (DELETE) — out of scope; используем
  деактивацию. Это упрощает целостность FK с журналом действий и
  отчётами.

### 6.3.0.3 🔧 BE — Защита существующих admin-эндпоинтов

**Описание:** Sweep-аудит всех существующих эндпоинтов backend на
предмет применения `require_admin` к тем, что должны быть доступны
только администраторам. До этой задачи такие эндпоинты защищены
только аутентификацией (любой залогиненный юзер имеет доступ),
что было приемлемо при модели "admin-only система", но недопустимо
после введения роли `user` через инвайты.

**Зависит от:** → 6.3.0.2

**DoD:**

- [x] Аудит-таблица в `docs/endpoint-roles.md` (полный список
      эндпоинтов с пометкой "admin-only" / "user+admin" / "public").
  - [x] Справочники (crops): GET — user+admin; POST/PUT/DELETE
        отложены до 6.3.2 — будут admin
  - [x] Настройки системы (`/api/settings/*`) — пока нет;
        зарезервированы как admin (см. таблицу "Future endpoints")
  - [x] Управление расписаниями/cron — UI отсутствует (cron внутри
        APScheduler), внешние эндпоинты не нужны
  - [x] Эндпоинты бэкапов (`/api/backup/*`) — пока нет;
        зарезервированы как admin
  - [x] Telegram-настройки: per-user bind (`/api/auth/telegram/*`)
        — user+admin; system-level настройки токена бота — пока нет
        (Future, admin)
  - [x] API-ключи внешних сервисов — пока через `.env` (не через
        API); Future endpoints в `/api/settings/api-keys` будут
        admin
  - [x] Файлы (`/api/events/{id}/photos`): user+admin (журнал
        общий, row-level вне scope)
  - [x] CRUD журнала/событий/отчётов — user+admin (общий журнал,
        нет per-user owner-FK; row-level — отдельная задача
        6.3.0.4 если потребуется)
  - [x] `/uploads/*` — публичный StaticFiles mount (UUID-имена, не
        перечислимы); ограничение задокументировано
- [x] Каждый admin-only эндпоинт получает зависимость
      `Depends(require_admin)`:
  - [x] `POST/PUT/DELETE /api/locations(/{id})`
  - [x] `POST/PUT/DELETE /api/alerts/rules(/{id})`
  - [x] `/api/admin/users/*` (уже было)
  - [x] `/api/admin/invites/*` (уже было)
- [x] Эндпоинты, доступные user'ам, явно используют
      `Depends(get_current_user)` — без анонимных дыр
- [x] Тесты `tests/test_endpoint_roles.py` (parametrized):
  - [x] Для каждого admin-эндпоинта: anonymous → 401, non-admin →
        403, admin → не 401/403 (role gate проходит)
  - [x] Регрессия: `test_locations.py` и `test_alert_rules.py`
        обновлены (admin happy path), все 331 теста проходят
- [x] `docs/endpoint-roles.md` — таблица "endpoint → required role"
      (вручную, по модулям `app/api/`)

**Замечания:**

- Бизнес-правило "user видит/редактирует только свои записи" vs
  "все видят всё" — out of scope этой задачи; здесь только role-
  level доступ. Row-level политики, если потребуются — отдельная
  задача (6.3.0.4 при необходимости).
- При обнаружении эндпоинта без какой-либо защиты (anonymous)
  который должен быть защищён — фиксировать как баг и закрывать
  здесь же.
- Список выше — стартовый чек-лист; реальный аудит должен быть
  исчерпывающим (пройти по всем роутерам в `app/api/`).

### 6.3.0-FE 🎨 FE — UI для ролей, инвайтов и управления юзерами

**Статус:** ✅ done

**Описание:** Frontend-часть для small team auth: admin-страница
управления пользователями, страница принятия инвайта, role-based
guards для роутов.

**Зависит от:** → 6.3.0.2

**Реализация:** Декомпозирован и реализован в задачах
6.3.0-FE.1 … 6.3.0-FE.4:

- 6.3.0-FE.1 — Foundation: auth store + AdminRoute + UI deps
- 6.3.0-FE.2 — Accept Invite page (публичная)
- 6.3.0-FE.3 — Admin Users page
- 6.3.0-FE.4 — Admin Invites page

DoD исходного эпика покрыт совокупно DoD под-задач FE.1–FE.4.

### 6.3 🔧 BE — Эндпоинты настроек (4 группы) ✅

**Описание:** API настроек по 4 группам (sources / api-keys / telegram / backup) с шифрованием секретов и маскировкой. Дизайн зафиксирован в [`docs/DECISIONS.md` → ADR-002](docs/DECISIONS.md) + amendment 2026-05-12.

**Зависит от:** → 6.3.0

**DoD:**

- [x] Эндпоинты (все требуют `Depends(require_admin)`):
  - [x] `GET /api/settings/sources`, `PUT /api/settings/sources`
  - [x] `GET /api/settings/api-keys`, `PUT /api/settings/api-keys`
  - [x] `GET /api/settings/telegram`, `PUT /api/settings/telegram`
  - [x] `GET /api/settings/backup`, `PUT /api/settings/backup`
- [x] Pydantic v2 схемы для каждой группы (отдельные Read/Update типы) — `backend/app/schemas/settings.py`
- [x] Хранение: одна строка на группу в существующей таблице `settings(key, value JSONB)`, ключи `sources | api_keys | telegram | backup`. Миграция не требовалась.
- [x] Шифрование секретов: Fernet, ключ выводится из `SECRET_KEY` через HKDF-SHA256 — `backend/app/core/encryption.py`
- [x] Resolver `backend/app/services/settings/resolver.py`: `get_secret(name)` возвращает DB → env → None (DB перекрывает env). Env читается через `get_settings().<ATTR>` (Pydantic-settings) для тест-однородности
- [x] Клиенты `openweathermap` (`is_configured()`, `_api_key()` → async + resolver), `telegram_bot.run()` (через `asyncio.run`), scheduler `_evaluate_alerts` читают секреты через resolver. `open_meteo`, `nasa_power` секретов не используют.
- [x] Маскировка в GET: секреты возвращаются как `"***" + value[-4:]`; пустые → `null`
- [x] PUT-семантика sentinel (см. ADR-002 Q3): null/absent → keep; начинается с `"***"` → keep; `""` → clear (fallback env); иначе → encrypt+save
- [x] Audit log на каждый PUT: `structlog.info("settings.updated", group=..., user_id=..., changed_keys=[...])`. Значения секретов не логируются — только имена полей
- [x] Тесты pytest (`backend/tests/test_settings.py`, 15 кейсов): happy GET/PUT каждой группы, маскировка last4, sentinel-mask=noop, sentinel-`""`→env, 403 non-admin (×4 параметризация), 401, resolver DB-override + env-fallback + None

**Реализация:**

- Yandex.Disk auth: оставлен WebDAV `login + app_password` (отход от ADR-002 Q5 OAuth-токена) — env parity с `.env.example`; client-кода ещё нет, переключаться дешёво. Поле `login` хранится в plain JSONB, шифруется только `app_password`.
- Sources group: `{priority: list[Source], enabled: dict[Source, bool], average_mode: bool}`. `enabled` дополняет `priority`, чтобы FE отличал "выключен" от "удалён из priority" без перестановки.
- Resolver: async с короткоживущей сессией, если session не передана. Sync-кеш отклонён — потребовал бы invalidation-hook на каждом PUT и плохо работал бы в multi-worker.
- Env fallback использует `get_settings().<ATTR>`, не `os.environ` — единый источник env-coercion (Pydantic-settings); тесты monkeypatch'ат Settings instance.

Изменения зафиксированы в DECISIONS.md amendment 2026-05-12.

### 6.3.1 🔧 BE — Смена пароля ✅

**Описание:** Эндпоинт смены пароля авторизованным пользователем.

**Зависит от:** → 1.4

**DoD:**

- [x] `POST /api/auth/change-password` (204 на успех)
- [x] Body: `{old_password: str, new_password: str}` (Pydantic v2, `ChangePasswordRequest` в `backend/app/schemas/auth.py`)
- [x] Валидация `new_password`: `min_length=8`, `max_length=128`, `model_validator(mode="after")` запрещает равенство `old_password` → 422
- [x] Проверка `verify_password(old_password, user.password_hash)` → 400 (`"Incorrect old password"`) если не совпадает
- [x] Хеш нового через `hash_password` (bcrypt, `passlib.CryptContext`) — как в логине
- [x] Auth: `Depends(get_current_user)`; без токена → 401
- [x] Инвалидация refresh-токенов: **N/A для MVP** — JWT stateless, refresh-токены в БД не хранятся (`backend/app/core/security.py` использует `jose.jwt`). Зафиксировано как known limitation: ADR-003 в `docs/DECISIONS.md`. Полное решение делегировано задаче `6.3.0-DEBT.2` (`User.tokens_invalidated_at` + проверка `iat >= tokens_invalidated_at` в `get_current_user`)
- [x] Audit log: `structlog.info("auth.password_changed", user_id=...)` (без значений и хешей)
- [x] Тесты pytest (`backend/tests/test_auth_change_password.py`, 5 кейсов):
  - [x] happy path: верный old → 204, login со старым → 401, login с новым → 200
  - [x] неверный old_password → 400 (`"Incorrect old password"`); старый пароль не меняется
  - [x] new_password слабый (<8) → 422; старый пароль не меняется
  - [x] new == old → 422 (`model_validator`, detail содержит `"must differ"`)
  - [x] 401 без токена

### 6.3.2 🔧 BE — Crops CRUD (admin) ✅

**Описание:** Расширить `app/api/crops.py` до полноценного CRUD справочника культур.

**Зависит от:** → 5.0.5, 6.3.0

**DoD:**

- [x] `POST /api/crops` (admin) — создать культуру
- [x] `PUT /api/crops/{id}` (admin) — обновить (partial-семантика, см. ADR-004)
- [x] `DELETE /api/crops/{id}` (admin) — см. ниже стратегию удаления
- [x] Pydantic v2 схемы: `CropCreate`, `CropUpdate` (поля: `name`, `base_temperature`, `optimal_temp_min`, `optimal_temp_max`)
- [x] Уникальность `name` (DB constraint + 409 при дубликате)
- [x] **Стратегия DELETE: `409 Conflict` при наличии связанных `field_events` или `location_crops`.** Обоснование:
  - soft delete усложняет фильтры FE и сидер (что делать при reseed уже soft-deleted культуры?)
  - cascade рискует: одно случайное `DELETE` сносит исторические события урожая → потеря данных журнала
  - 409 безопасен и явен; admin сначала чистит/мигрирует связанные записи, потом удаляет
  - response 409 (FastAPI оборачивает в `{"detail": ...}`):
    `{detail: {message: "Crop is referenced by N field_events / M location_crops", references: {field_events: N, location_crops: M}}}`
- [x] Все мутирующие эндпоинты — `Depends(require_admin)`
- [x] Тесты pytest (`backend/tests/test_admin_crops.py`, 13 кейсов):
  - [x] POST happy + 409 на дубликат имени
  - [x] PUT happy + 404 на несуществующий + 409 на дубликат при переименовании
  - [x] DELETE happy (нет связанных)
  - [x] DELETE → 409 при наличии `field_events` (создать через фикстуру)
  - [x] DELETE → 409 при наличии `location_crops`
  - [x] не-admin → 403, неавторизованный → 401

**Реализация:**

- Admin-ручки живут под `/api/crops` рядом с публичным GET, а не под `/api/admin/crops`. `require_admin` навешен пометодно (POST/PUT/DELETE), публичный GET сохранён под `get_current_user`. Решение зафиксировано в ADR-004 (`docs/DECISIONS.md`).
- Для admin-просмотра используется существующий `GET /api/crops`; отдельные `GET /api/admin/crops` и `GET /api/admin/crops/{id}` намеренно не создавались.
- PUT работает как partial update (`model_dump(exclude_unset=True)`) — фактически PATCH-семантика на PUT-методе. Решение зафиксировано в ADR-004.
- Миграция не требуется: модель `Crop` уже содержит `UNIQUE` на `name` и необходимые поля (`20260428_0002_create_all_tables`).

### 6.3.0-DEBT — Технический долг по эпику ролей

#### 6.3.0-DEBT.1 🔧 BE — Fix accept-url contract drift

**Описание:** backend `build_invite_url` отдаёт URL в формате
`?token=...` (query), FE использует path-формат
`/accept-invite/{token}`. На текущем этапе работает, потому что FE
собирает URL сам и игнорирует `invite_url` из ответа. При появлении
email/Telegram-рассылок инвайтов backend будет рассылать невалидные
ссылки.

**Зависит от:** → 6.3.0.1
**Блокирует:** рассылку инвайтов через email/Telegram

**Статус:** ✅ выполнено 2026-05-12

**DoD:**

- [x] `build_invite_url` в `app/services/invites.py` возвращает path-формат:
      `${FRONTEND_URL}/accept-invite/{token}`
- [ ] FE `CreateInviteDialog` (стадия 2) использует
      `response.invite_url` напрямую вместо самосборки
      *(FE-задача — вне scope этого коммита)*
- [x] Тест `test_admin_creates_invite`: `invite_url` оканчивается на
      `/accept-invite/{token}` и не содержит `?`
- [x] ADR-005 в `docs/DECISIONS.md` фиксирует path-формат как контракт

#### 6.3.0-DEBT.2 🔧 BE — JWT invalidation после смены пароля и деактивации

**Описание:** refresh-токены stateless (jose.jwt). После смены пароля
через 6.3.1 или деактивации юзера через `/admin/users/{id}` старый
refresh-токен остаётся валидным до естественного истечения (7 дней).
Это known limitation MVP, зафиксированное в DoD задачи 6.3.1.

**Зависит от:** → 6.3.0, 6.3.1
**Блокирует:** прод-деплой (6.6) — security gate

**Статус:** ✅ выполнено 2026-05-12

**DoD:**

- [x] Колонка `User.tokens_invalidated_at TIMESTAMPTZ NULL`
      (миграция Alembic `0012_user_tokens_invalidated_at.py`)
- [x] При смене пароля и при `is_active=False` через admin —
      `tokens_invalidated_at = now(UTC)`
- [x] `get_current_user` валидирует:
      `int(iat) > int(tokens_invalidated_at.timestamp())` иначе 401
      (`_token_invalidated` в `app/api/deps.py`). Refresh-эндпоинт делает
      ту же проверку (закрывает loophole из ADR-003).
- [x] Тесты в `backend/tests/test_jwt_invalidation.py`:
  - [x] смена пароля → старый refresh не работает (401 «Token invalidated»)
  - [x] деактивация → старый access не работает (401)
  - [x] реактивация → новые токены работают (через `time.sleep(1.1)` —
        iat-секунда строго после invalidated-секунды)

**Решение «не сбрасывать tokens_invalidated_at при реактивации»** —
security choice: если у злоумышленника был токен ДО deactivation, он
должен оставаться мёртвым и после reactivation. Цена: после реактивации
пользователь должен подождать ≥ 1 секунду перед login (в production
это не проблема — обычно проходят минуты).

#### 6.3.0-DEBT.3 ⚙️ FE-F — Code-splitting frontend бандла

**Описание:** текущий бандл 2.55 MB (gzip 815 KB), Vite пишет warning
`>500kB`. На медленных каналах TTI неприемлемый.

**Зависит от:** → none
**Блокирует:** прод-деплой (6.6) — UX gate

**DoD:**

- [x] Все роуты страниц обёрнуты в `React.lazy` + `<Suspense>` с
      loading-skeleton
- [x] `vite.config.ts` `manualChunks`:
  - recharts → отдельный чанк
  - plotly.js + react-plotly.js → отдельный чанк
  - react/react-dom/react-router → vendor-чанк
- [x] Главный чанк ≤ 500 KB (gzip)
- [x] `pnpm build` без warning'а про размер
- [x] Smoke: переход между всеми страницами работает, lazy-загрузка
      видна в Network таб'е

### 6.4 ⚙️ FE-F — Страница «Настройки» ✅

**Зависит от:** → 6.2, 6.3, 6.3.1, 6.3.2
**DoD:**

- [x] Вкладки: «Источники данных», «API-ключи», «Telegram», «Бэкапы», «Культуры», «Профиль»
- [x] Формы для каждой вкладки
- [x] Кнопка «Привязать Telegram» (генерация кода) — `POST /api/auth/telegram/bind-code`
- [ ] Кнопка «Сделать бэкап сейчас» — UI присутствует (disabled), активируется при реализации `POST /api/backup/run` в задаче 6.2
- [ ] Список бэкапов с возможностью скачать (через Яндекс.Диск) — пустой стейт с пометкой про ожидание задачи 6.2 (`GET /api/backup/list`)
- [x] Управление справочником культур (CRUD, базовая температура для GDD)
- [x] Смена пароля — `POST /api/auth/change-password`

**Реализация:**

- Активная вкладка хранится в URL (`?tab=sources|api-keys|telegram|backup|crops|profile`)
- Admin-вкладки (Источники / API-ключи / Telegram / Бэкапы / Культуры) скрыты для не-admin пользователей; не-admin видит только «Профиль». Если admin-эндпоинт вернёт 403, форма показывает `AdminOnlyNotice`
- Tabs реализованы через стандартный `@radix-ui/react-tabs` + новый `src/components/ui/tabs.tsx` (стандартный шаблон shadcn без визуальной кастомизации)
- Все формы используют TanStack Query (`useQuery` / `useMutation`); состояния loading / error / empty / success обработаны
- Бэкап-секция (ручной запуск + список) заглушена до выполнения задачи 6.2

### 6.5 🚀 INFRA — Nginx + HTTPS ✅

**DoD:**

- [x] `nginx/nginx.conf` — reverse proxy на backend (`/api`) и frontend (`/`)
- [x] Раздача `/uploads/` напрямую через nginx
- [x] Gzip, кэширование статики
- [x] Сертификат Let's Encrypt (certbot в отдельном контейнере)
- [x] Автообновление сертификата (cron)
- [x] HTTP → HTTPS редирект
- [ ] Тест: SSL Labs grade A — проверить после деплоя на VPS

### 6.6 🚀 INFRA — Production deploy ✅

**DoD:**

- [x] `docker-compose.prod.yml` (без hot-reload, с restart policies)
- [x] Healthchecks для всех сервисов (db, backend, frontend, telegram_bot, nginx)
- [x] Логи в JSON-формате, монтирование на хост (nginx — bind-mount `./logs/nginx`; остальные — docker `json-file` driver с ротацией 10MB × 5)
- [x] Скрипт `scripts/deploy.sh` для обновления (git ff → pull/build → up -d → migrate → prune)
- [ ] Развёрнуто на VPS, открывается по домену — проверяется на VPS вручную
- [ ] Backend и frontend работают через HTTPS — проверяется на VPS вручную

### 6.7 📚 DOCS — Документация ✅

**DoD:**

- [x] `README.md`: описание, требования, быстрый старт (dev) — обновлён индекс документации
- [x] `docs/DEPLOY.md`: инструкция по деплою на VPS (6.5/6.6 + актуальный раздел логов и `deploy.sh`)
- [x] `docs/BACKUP.md`: настройка Яндекс.Диска (WebDAV), ротация, restore в работающий стенд и в чистое окружение; помечено, что job/restore-CLI ждут реализации 6.2
- [x] `docs/API.md`: ссылка на Swagger + curl-сценарии по группам (auth, locations, weather, analytics, alerts, events, reports, settings, telegram, health) + коды ошибок и CORS
- [x] `docs/TELEGRAM.md`: BotFather → токен → `.env`/UI → bind-code flow → команды → безопасность
- [x] CHANGELOG.md (Keep a Changelog 1.1.0, заполнен из истории git)

---

## Этап 7: Визуальная стилизация (FE-V)

> Все задачи этого этапа выполняются после того, как функциональные версии страниц готовы и работают.

### 7.1 🎨 FE-V — Дизайн-токены и темы

**Описание:** Базовая система цветов, типографики, отступов.
**DoD:**

- [x] `src/styles/tokens.css` — CSS-переменные для двух стилей (Apple / Notion)
- [x] Подключён шрифт Inter (как замена SF Pro)
- [x] Tailwind config расширен токенами
- [x] Светлая и тёмная темы для обоих стилей
- [x] Демо-страница `/styleguide` (только в dev) с примерами компонентов

### 7.2 🎨 FE-V — Apple HIG: Дашборд

**Зависит от:** → 2.6, 7.1
**DoD:**

- [x] Карточки локаций: скругления 16–20px, мягкие тени, увеличенные отступы
- [x] Типографика: крупные заголовки, чёткая иерархия
- [x] Акцентные цвета (системный синий #007AFF и пастельные)
- [x] Hover-эффекты на карточках (subtle lift)
- [x] Skeleton loaders в стиле Apple
- [x] Адаптивность сохранена
- [x] Тёмная тема выглядит как iOS dark mode
- [x] Логика не изменена (diff только в стилях/классах)

### 7.3 🎨 FE-V — Apple HIG: Layout (sidebar, header)

**Зависит от:** → 2.4, 7.1
**DoD:**

- [ ] Sidebar: полупрозрачность, blur backdrop
- [ ] Иконки в стиле SF Symbols (lucide-react с подходящим набором)
- [ ] Плавные переходы при сворачивании sidebar
- [ ] Mobile drawer с анимацией slide

### 7.4 🎨 FE-V — Apple HIG: Графики и Аналитика

**Зависит от:** → 3.6, 3.8, 7.1
**DoD:**

- [ ] Карточки-обёртки графиков в стиле Apple
- [ ] Цветовая палитра графиков (мягкие, насыщенные)
- [ ] Tooltips в стиле iOS
- [ ] Кнопки и фильтры — закруглённые, с focus-rings

### 7.5 🎨 FE-V — Notion-style: Таблицы

**Зависит от:** → 3.7, 7.1
**DoD:**

- [ ] Минимальные границы, тонкие разделители
- [ ] Плотная компоновка строк
- [ ] Hover на строке: лёгкий фон
- [ ] Sticky header при скролле
- [ ] Шрифт Inter, моноширинный для чисел
- [ ] Иконки колонок (тип данных)
- [ ] Условное форматирование с пастельными фонами

### 7.6 🎨 FE-V — Notion-style: Журнал событий

**Зависит от:** → 5.4, 7.1
**DoD:**

- [ ] Карточки событий: минимализм, тонкие границы
- [ ] Drag-n-drop сортировка (опционально)
- [ ] Inline-редактирование заголовка
- [ ] Галерея фото в стиле Notion (grid + lightbox)
- [ ] Фильтры в виде «чипов»

### 7.7 🎨 FE-V — Notion-style: Настройки и Алерты

**Зависит от:** → 4.5, 6.4, 7.1
**DoD:**

- [ ] Левое меню вкладок в стиле Notion
- [ ] Формы с лёгкими полями (без жирных границ)
- [ ] Toggle-переключатели в Notion-стиле
- [ ] Списки правил алертов как блоки

### 7.8 🎨 FE-V — Анимации и микровзаимодействия

**DoD:**

- [ ] Framer Motion подключён
- [ ] Плавные переходы между страницами (fade)
- [ ] Анимация появления карточек (stagger)
- [ ] Toast-уведомления (sonner / shadcn toast)
- [ ] Loading states унифицированы

### 7.9 🎨 FE-V — Финальная адаптивная проверка

**DoD:**

- [ ] Все страницы протестированы на 360px, 768px, 1024px, 1440px
- [ ] Touch-friendly размеры на mobile (min 44px)
- [ ] Нет горизонтального скролла
- [ ] Графики корректно ресайзятся

---

## Этап 8 (будущее, не входит в MVP): ML

### 8.1 🔧 BE — Сбор обучающей выборки

- Объединение данных погоды и журнала урожая в датасет
- Экспорт в CSV/parquet для исследования

### 8.2 🔧 BE — Базовые модели

- Регрессия: GDD → срок созревания
- Регрессия: погода + культура → урожайность

### 8.3 ⚙️ FE-F — Раздел «Прогноз урожая»

- UI для запуска прогноза, отображения результатов

---

## Карта зависимостей (упрощённая)

```
0.1 → 0.2
0.2 → 1.1 → 1.2 → 1.3 → 1.4 → 1.5
                        ↓
                       1.6, 1.7, 1.8 → 1.9 → 1.10 → 1.11

2.1 → 2.2 → 2.3 → 2.4 → 2.5, 2.6

3.1, 3.2, 3.3 → 3.4
              → 3.5
3.1 → 3.6
3.2 → 3.7
3.3, 3.4, 3.5 → 3.8

4.1 → 4.2, 4.4.0, 4.4.1, 4.5
4.2 → 4.2.1
4.3 → 4.4
4.2, 4.3 → 4.4
4.2 → 4.4.0
4.4.0 → 4.4.1
4.4.1 → 4.5

5.1 → 5.2, 5.4
5.1, 3.2, 3.4 → 5.3 → 5.3.1 → 5.5

1.4 → 6.3.0 → 6.3, 6.3.2
1.4 → 6.3.1
5.0.5 → 6.3.2
6.2, 6.3, 6.3.1, 6.3.2 → 6.4
6.5 → 6.6 → 6.7

7.1 → 7.2..7.9
```

---

## Чек-лист порядка работы

**Рекомендуемый порядок выполнения:**

1. ✅ Этап 0 (инициализация) — 1 день
2. ✅ Этап 1 (backend MVP) — 5–7 дней
3. ✅ Этап 2 (frontend каркас + локации + дашборд) — 3–4 дня
4. ✅ Проверка end-to-end: добавить локацию, увидеть данные → **первый working demo**
5. ✅ Этап 3 (анализ данных) — 5–6 дней
6. ✅ Этап 4 (алерты + Telegram) — 3–4 дня
7. ✅ Этап 5 (журнал + отчёты) — 4–5 дней
8. ✅ Этап 6 (прод-готовность) — 3–4 дня
9. ✅ **Деплой на VPS, использование в реальной жизни**
10. ✅ Этап 7 (визуальная стилизация) — 4–6 дней (можно растянуть)
11. ⏳ Этап 8 (ML) — когда наберётся достаточно данных журнала (через сезон)

**Принцип:** сначала всё работает функционально, потом полируется визуально.
