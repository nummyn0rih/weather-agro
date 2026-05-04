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

### 6.1.1 🔧 BE — Fix: TZ-aware агрегация в OpenWeatherMap forecast

Зависит от: → 6.1
Блокирует: интеграцию OWM как источника alerts engine

DoD:

- [ ] `fetch_forecast` группирует 3h-бакеты по локальной TZ локации
- [ ] TZ берётся из `Location.timezone` (новое поле, nullable, default UTC) ИЛИ вычисляется через `timezonefinder` из (lat, lon)
- [ ] Решение зафиксировано в ADR (новый или дополнение к существующему)
- [ ] Тест: для локации UTC+3 заморозок в 02:00 локального попадает в правильный день
- [ ] `fetch_current.d` тоже использует локальную TZ (или явно документировано почему UTC ок для current)

### 6.2 🔧 BE — Бэкапы на Яндекс.Диск

**Описание:** Автоматические бэкапы БД.
**DoD:**

- [ ] `app/services/backup/yandex_disk.py` (WebDAV-клиент)
- [ ] Скрипт `pg_dump` → gzip → upload на Яндекс.Диск
- [ ] Cron-задача (04:00 МСК)
- [ ] Ротация: 30 ежедневных + 12 ежемесячных
- [ ] `POST /api/backup/run` — ручной запуск
- [ ] `GET /api/backup/list` — список бэкапов на Яндекс.Диске
- [ ] CLI-скрипт восстановления `scripts/restore.py`
- [ ] Логирование в БД (таблица `backup_logs`)

### 6.3.0 🔧 BE — Роли пользователей и активность

**Описание:** Добавление поля `is_admin` и `is_active` к модели `User`,
dependency `require_admin`, проверка `is_active` при логине и в
`get_current_user`. Базис для admin-эндпоинтов и инвайтов.

**Зависит от:** → 1.4 (auth уже реализован), → 1.3 (модели/миграции)

**DoD:**

- [ ] Миграция Alembic: добавляет колонки в `users`
  - [ ] `is_admin BOOLEAN NOT NULL DEFAULT FALSE`
  - [ ] `is_active BOOLEAN NOT NULL DEFAULT TRUE`
  - [ ] Backfill: `is_admin=true` для пользователя с
        `username == ${ADMIN_USERNAME}` (env)
  - [ ] Все существующие пользователи получают `is_active=true`
- [ ] Обновлена SQLAlchemy-модель `User` — добавлены оба поля
- [ ] Сидер при создании admin устанавливает `is_admin=true`,
      `is_active=true`; при наличии существующего admin —
      проверяет/чинит флаги (idempotent)
- [ ] Dependency `require_admin` в `app/api/deps.py`:
  - [ ] Использует `get_current_user`
  - [ ] Возвращает 403 если `is_admin=False`
  - [ ] Возвращает 401 если пользователь неактивен (защита глубже)
- [ ] `get_current_user` дополнительно проверяет `is_active=True`,
      иначе 401 с сообщением "User is inactive"
- [ ] Login endpoint проверяет `is_active=True` перед выдачей токена,
      иначе 401 "User is inactive"
- [ ] Тесты:
  - [ ] `require_admin` пропускает admin
  - [ ] `require_admin` возвращает 403 для обычного user
  - [ ] `require_admin` возвращает 401 для неавторизованного запроса
  - [ ] Логин неактивного пользователя → 401
  - [ ] `get_current_user` с токеном неактивного юзера → 401
  - [ ] Сидер на повторном запуске не дублирует и не сбрасывает флаги
- [ ] Эндпоинт `GET /api/auth/me` возвращает поля `is_admin`,
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

- [ ] Миграция Alembic: таблица `invites`
  - [ ] `id` PK
  - [ ] `username VARCHAR(255) NOT NULL` (по соглашению — email)
  - [ ] `is_admin BOOLEAN NOT NULL DEFAULT FALSE`
  - [ ] `token VARCHAR(64) UNIQUE NOT NULL` (URL-safe random)
  - [ ] `created_by_id` FK → users.id
  - [ ] `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - [ ] `expires_at TIMESTAMPTZ NOT NULL`
  - [ ] `accepted_at TIMESTAMPTZ NULL`
  - [ ] `revoked_at TIMESTAMPTZ NULL`
  - [ ] Индекс по `token`
- [ ] SQLAlchemy-модель `Invite`
- [ ] Pydantic-схемы:
  - [ ] `InviteCreate { username: EmailStr, is_admin: bool = False }`
  - [ ] `InviteRead` (без token при list)
  - [ ] `InviteAccept { password: str (min 8) }`
- [ ] Сервис `app/services/invites.py`:
  - [ ] `create_invite(session, username, is_admin, created_by)` —
        генерит token (`secrets.token_urlsafe(32)`),
        `expires_at = now() + 7 days`. Если username уже занят
        активным юзером — 409. Если уже есть активный неиспользованный
        инвайт на этот username — 409 (можно сначала revoke).
  - [ ] `revoke_invite(session, invite_id)` — ставит `revoked_at`
  - [ ] `get_invite_by_token(session, token)` — валидирует:
        не accepted, не revoked, не expired
  - [ ] `accept_invite(session, token, password)` — создаёт User
        (`is_admin` из инвайта, `is_active=True`, bcrypt-хеш),
        ставит `accepted_at`, возвращает User
- [ ] Эндпоинты:
  - [ ] `POST /api/admin/invites` — `require_admin`,
        body `InviteCreate`, ответ `{id, token, invite_url}`,
        `invite_url` собирается из `FRONTEND_URL` env +
        `/accept-invite?token=...`
  - [ ] `GET /api/admin/invites` — `require_admin`, список всех
        инвайтов со статусами (pending/accepted/revoked/expired)
  - [ ] `DELETE /api/admin/invites/{id}` — `require_admin`,
        revoke. 404 если уже accepted.
  - [ ] `GET /api/auth/invites/{token}` — публичный, валидирует
        токен, возвращает `{username, is_admin}` для отображения на
        форме accept-invite. 404/410 при невалидном токене.
  - [ ] `POST /api/auth/invites/{token}/accept` — публичный,
        body `InviteAccept`, создаёт User, возвращает access+refresh
        токены (auto-login)
- [ ] Rate limiting через slowapi на публичных эндпоинтах
      `/api/auth/invites/*`
- [ ] Тесты:
  - [ ] Admin создаёт инвайт → 201 с token и invite_url
  - [ ] Не-admin создаёт инвайт → 403
  - [ ] Создание инвайта на существующий username → 409
  - [ ] GET по валидному токену → 200 с username/is_admin
  - [ ] GET по revoked токену → 410
  - [ ] GET по expired токену → 410
  - [ ] GET по accepted токену → 410
  - [ ] Accept валидного инвайта → 200, юзер создан, токены выданы
  - [ ] Accept того же токена дважды → второй раз 410
  - [ ] Revoke инвайта → 204; последующий GET → 410
  - [ ] Revoke accepted инвайта → 404
  - [ ] List возвращает все статусы корректно

**Замечания:**

- `FRONTEND_URL` добавить в `.env.example`
- Поле `username` в `InviteCreate` валидируется как `EmailStr`
- Вычисление статуса "expired" — на лету при чтении, не cron

### 6.3.0.2 🔧 BE — Admin-эндпоинты управления пользователями

**Описание:** Список пользователей, сброс пароля, деактивация/
активация, изменение роли.

**Зависит от:** → 6.3.0.1

**DoD:**

- [ ] Pydantic-схемы:
  - [ ] `UserRead { id, username, is_admin, is_active, created_at }`
  - [ ] `UserPasswordReset { password: str (min 8) }`
  - [ ] `UserUpdate { is_admin?: bool, is_active?: bool }`
- [ ] Эндпоинты (все `require_admin`):
  - [ ] `GET /api/admin/users` — список всех пользователей
  - [ ] `GET /api/admin/users/{id}` — один пользователь
  - [ ] `PATCH /api/admin/users/{id}` — обновление is_admin/is_active
  - [ ] `POST /api/admin/users/{id}/reset-password` —
        body `UserPasswordReset`, обновляет хеш пароля
- [ ] Защита от self-lockout:
  - [ ] Admin не может снять `is_admin` с самого себя → 400
  - [ ] Admin не может деактивировать самого себя → 400
  - [ ] Нельзя удалить/деактивировать последнего активного admin'a
        → 400 с понятным сообщением
- [ ] Тесты:
  - [ ] Admin видит список юзеров
  - [ ] Не-admin → 403
  - [ ] Сброс пароля работает (старый не подходит, новый подходит)
  - [ ] Деактивация юзера → юзер не может залогиниться
  - [ ] Реактивация → может
  - [ ] Self-demote → 400
  - [ ] Self-deactivate → 400
  - [ ] Деактивация последнего admin'a → 400
  - [ ] Снятие is_admin с последнего admin'a → 400

**Замечания:**

- Удаление пользователя (DELETE) — out of scope; используем
  деактивацию. Это упрощает целостность FK с журналом действий и
  отчётами.

### 6.3.0-FE 🎨 FE — UI для ролей, инвайтов и управления юзерами

**Описание:** Frontend-часть для small team auth: admin-страница
управления пользователями, страница принятия инвайта, role-based
guards для роутов.

**Зависит от:** → 6.3.0.2

**DoD:**

- [ ] Стор/контекст auth расширен: `user.is_admin`, `user.is_active`
      доступны после логина и через `/api/auth/me`
- [ ] Route guard `<RequireAdmin>` — редиректит не-admin'ов с
      admin-страниц на dashboard с toast "Доступ запрещён"
- [ ] Страница `/admin/users`:
  - [ ] Таблица: username, роль (admin/user), статус (активен/нет),
        дата создания
  - [ ] Кнопка "Создать инвайт" → модалка
        (поле email с валидацией, чекбокс "admin")
  - [ ] После создания — модалка с готовой инвайт-ссылкой и
        кнопкой "Копировать"
  - [ ] Действия в строке: "Сбросить пароль", "Деактивировать"/
        "Активировать", "Сделать admin"/"Снять admin"
  - [ ] Подтверждения для деструктивных действий
  - [ ] Серверные ошибки 400 (self-lockout) показываются в toast
- [ ] Страница `/admin/invites`:
  - [ ] Список инвайтов со статусами (pending/accepted/revoked/
        expired)
  - [ ] Для pending — кнопки "Скопировать ссылку", "Отозвать"
  - [ ] (можно объединить с `/admin/users` — на усмотрение
        реализатора, но в DoD как отдельная страница для ясности)
- [ ] Страница `/accept-invite?token=...` (публичная):
  - [ ] При загрузке — `GET /api/auth/invites/{token}`
  - [ ] Если токен невалиден/expired/revoked/accepted —
        показать соответствующее сообщение
  - [ ] Если валиден — форма: показывает username (readonly),
        поле "Пароль", "Повтор пароля", кнопка "Создать аккаунт"
  - [ ] После успешного accept — auto-login (токены сохранены) и
        редирект на dashboard
- [ ] В layout/sidebar пункт "Управление пользователями" виден
      только admin'ам
- [ ] Login-форма: при ответе 401 "User is inactive" — показать
      понятное сообщение "Учётная запись отключена. Обратитесь к
      администратору."

**Замечания:**

- Дизайн в стиле существующих admin-страниц (справочники)
- Email-валидация на форме инвайта — нативная HTML5 + бэк всё равно валидирует EmailStr

### 6.3 🔧 BE — Эндпоинты настроек (4 группы)

**Описание:** API настроек по 4 группам (sources / api-keys / telegram / backup) с шифрованием секретов и маскировкой. Дизайн зафиксирован в [`docs/DECISIONS.md` → ADR-002](docs/DECISIONS.md).

**Зависит от:** → 6.3.0

**DoD:**

- [ ] Эндпоинты (все требуют `Depends(require_admin)`):
  - [ ] `GET /api/settings/sources`, `PUT /api/settings/sources`
  - [ ] `GET /api/settings/api-keys`, `PUT /api/settings/api-keys`
  - [ ] `GET /api/settings/telegram`, `PUT /api/settings/telegram`
  - [ ] `GET /api/settings/backup`, `PUT /api/settings/backup`
- [ ] Pydantic v2 схемы для каждой группы (отдельные input/output типы)
- [ ] Хранение: одна строка на группу в существующей таблице `settings(key, value JSONB)`, ключи `sources | api_keys | telegram | backup`
- [ ] Шифрование секретов: Fernet, ключ выводится из `SECRET_KEY` через HKDF (`app/core/security.py`)
- [ ] Resolver `app/services/settings/resolver.py`: `get_secret(name)` возвращает DB → env → None (DB перекрывает env когда задано)
- [ ] Все клиенты (`open_meteo`, `openweathermap`, `nasa_power`, `yandex_disk`, `telegram_bot`) читают секреты через resolver, не напрямую из `os.environ`
- [ ] Маскировка в GET: секреты возвращаются как `"***" + value[-4:]`; пустые → `null`
- [ ] PUT-семантика sentinel (см. ADR-002 Q3):
  - поле отсутствует / `null` → не менять
  - значение начинается с `"***"` → не менять (round-trip GET-payload идемпотентен)
  - пустая строка `""` → удалить из БД (fallback на env)
  - любая другая строка → зашифровать и сохранить
- [ ] Audit log на каждый PUT: `structlog.info("settings.updated", group=..., user_id=..., changed_keys=[...])`. **Значения секретов НЕ логируются** — только имена изменённых полей
- [ ] Тесты pytest:
  - [ ] happy path для каждой группы (GET → PUT → GET)
  - [ ] маскировка last4
  - [ ] sentinel: PUT с маской → значение не меняется
  - [ ] PUT с `""` → секрет удалён, GET даёт env-значение
  - [ ] не-admin (`is_admin=False`) → 403
  - [ ] неавторизованный → 401
  - [ ] resolver: DB перекрывает env; при отсутствии DB-значения возвращает env

### 6.3.1 🔧 BE — Смена пароля

**Описание:** Эндпоинт смены пароля авторизованным пользователем.

**Зависит от:** → 1.4

**DoD:**

- [ ] `POST /api/auth/change-password`
- [ ] Body: `{old_password: str, new_password: str}` (Pydantic v2)
- [ ] Валидация `new_password`: min 8 символов, не равен `old_password`
- [ ] Проверка `verify_password(old_password, user.password_hash)` → 400 если не совпадает
- [ ] Хеш нового через `bcrypt` (как в логине)
- [ ] Auth: `Depends(get_current_user)`
- [ ] Инвалидация refresh-токенов: **N/A для MVP** — JWT stateless, refresh-токены в БД не хранятся (`backend/app/core/security.py` использует `jose.jwt`). Документировать как known limitation: после смены пароля старый refresh остаётся валидным до истечения (7 дней). Полное решение — `User.password_changed_at` + проверка `iat >= password_changed_at` в `get_current_user` — отложено до отдельной задачи (создать issue, не в рамках 6.3.1)
- [ ] Audit log: `structlog.info("auth.password_changed", user_id=...)` (без значений)
- [ ] Тесты pytest:
  - [ ] happy path: верный old → 204, новый пароль работает в `/login`
  - [ ] неверный old_password → 400
  - [ ] new_password слабый (<8) → 422
  - [ ] new == old → 400
  - [ ] 401 без токена

### 6.3.2 🔧 BE — Crops CRUD (admin)

**Описание:** Расширить `app/api/crops.py` до полноценного CRUD справочника культур.

**Зависит от:** → 5.0.5, 6.3.0

**DoD:**

- [ ] `POST /api/crops` (admin) — создать культуру
- [ ] `PUT /api/crops/{id}` (admin) — обновить
- [ ] `DELETE /api/crops/{id}` (admin) — см. ниже стратегию удаления
- [ ] Pydantic v2 схемы: `CropCreate`, `CropUpdate` (поля: `name`, `base_temperature`, `optimal_temp_min`, `optimal_temp_max`)
- [ ] Уникальность `name` (DB constraint + 409 при дубликате)
- [ ] **Стратегия DELETE: `409 Conflict` при наличии связанных `field_events` или `location_crops`.** Обоснование:
  - soft delete усложняет фильтры FE и сидер (что делать при reseed уже soft-deleted культуры?)
  - cascade рискует: одно случайное `DELETE` сносит исторические события урожая → потеря данных журнала
  - 409 безопасен и явен; admin сначала чистит/мигрирует связанные записи, потом удаляет
  - response 409: `{detail: "Crop is referenced by N field_events / M location_crops", references: {field_events: N, location_crops: M}}`
- [ ] Все мутирующие эндпоинты — `Depends(require_admin)`
- [ ] Тесты pytest:
  - [ ] POST happy + 409 на дубликат имени
  - [ ] PUT happy + 404 на несуществующий + 409 на дубликат при переименовании
  - [ ] DELETE happy (нет связанных)
  - [ ] DELETE → 409 при наличии `field_events` (создать через фикстуру)
  - [ ] DELETE → 409 при наличии `location_crops`
  - [ ] не-admin → 403, неавторизованный → 401

### 6.4 ⚙️ FE-F — Страница «Настройки»

**Зависит от:** → 6.2, 6.3, 6.3.1, 6.3.2
**DoD:**

- [ ] Вкладки: «Источники данных», «API-ключи», «Telegram», «Бэкапы», «Культуры», «Профиль»
- [ ] Формы для каждой вкладки
- [ ] Кнопка «Привязать Telegram» (генерация кода)
- [ ] Кнопка «Сделать бэкап сейчас»
- [ ] Список бэкапов с возможностью скачать (через Яндекс.Диск)
- [ ] Управление справочником культур (CRUD, базовая температура для GDD)
- [ ] Смена пароля

### 6.5 🚀 INFRA — Nginx + HTTPS

**DoD:**

- [ ] `nginx/nginx.conf` — reverse proxy на backend (`/api`) и frontend (`/`)
- [ ] Раздача `/uploads/` напрямую через nginx
- [ ] Gzip, кэширование статики
- [ ] Сертификат Let's Encrypt (certbot в отдельном контейнере)
- [ ] Автообновление сертификата (cron)
- [ ] HTTP → HTTPS редирект
- [ ] Тест: SSL Labs grade A

### 6.6 🚀 INFRA — Production deploy

**DoD:**

- [ ] `docker-compose.prod.yml` (без hot-reload, с restart policies)
- [ ] Healthchecks для всех сервисов
- [ ] Логи в JSON-формате, монтирование на хост
- [ ] Скрипт `deploy.sh` для обновления (git pull → docker compose pull → up -d)
- [ ] Развёрнуто на VPS, открывается по домену
- [ ] Backend и frontend работают через HTTPS

### 6.7 📚 DOCS — Документация

**DoD:**

- [ ] `README.md`: описание, требования, быстрый старт (dev)
- [ ] `docs/DEPLOY.md`: инструкция по деплою на VPS
- [ ] `docs/BACKUP.md`: настройка Яндекс.Диска, восстановление
- [ ] `docs/API.md`: ссылка на Swagger + основные сценарии
- [ ] `docs/TELEGRAM.md`: создание бота, привязка
- [ ] CHANGELOG.md

---

## Этап 7: Визуальная стилизация (FE-V)

> Все задачи этого этапа выполняются после того, как функциональные версии страниц готовы и работают.

### 7.1 🎨 FE-V — Дизайн-токены и темы

**Описание:** Базовая система цветов, типографики, отступов.
**DoD:**

- [ ] `src/styles/tokens.css` — CSS-переменные для двух стилей (Apple / Notion)
- [ ] Подключён шрифт Inter (как замена SF Pro)
- [ ] Tailwind config расширен токенами
- [ ] Светлая и тёмная темы для обоих стилей
- [ ] Демо-страница `/styleguide` (только в dev) с примерами компонентов

### 7.2 🎨 FE-V — Apple HIG: Дашборд

**Зависит от:** → 2.6, 7.1
**DoD:**

- [ ] Карточки локаций: скругления 16–20px, мягкие тени, увеличенные отступы
- [ ] Типографика: крупные заголовки, чёткая иерархия
- [ ] Акцентные цвета (системный синий #007AFF и пастельные)
- [ ] Hover-эффекты на карточках (subtle lift)
- [ ] Skeleton loaders в стиле Apple
- [ ] Адаптивность сохранена
- [ ] Тёмная тема выглядит как iOS dark mode
- [ ] Логика не изменена (diff только в стилях/классах)

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
