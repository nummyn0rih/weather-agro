# Changelog

Все значимые изменения проекта фиксируются в этом файле.

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/).

До 1.0 — minor-веха ≈ закрытый этап `TASKS.md`. Breaking-изменения API
допустимы между minor-вехами MVP.

## [Unreleased]

### Added
- FE-V (7.1) — дизайн-токены и темы:
  - `frontend/src/styles/tokens.css` — CSS-переменные двух стилей (Apple HIG
    и Notion-style), светлая и тёмная темы.
  - Шрифты Inter и JetBrains Mono подключены через Google Fonts.
  - `tailwind.config.js` расширен токенами: цвета (`apple-*`, `notion-*`),
    радиусы (`rounded-apple-{sm,md,lg,xl}`, `rounded-notion-*`), тени
    (`shadow-apple-{sm,md,lg,xl}`), display-кегли, easing `ease-apple`.
  - Страница `/styleguide` (только в dev) с примерами типографики,
    палитры, карточек, теней, таблиц и чипов.
- Документация:
  - [`docs/BACKUP.md`](docs/BACKUP.md) — настройка Яндекс.Диск (WebDAV),
    ротация, ручной запуск, восстановление в работающий стенд и в чистое
    окружение.
  - [`docs/API.md`](docs/API.md) — обзор endpoints с примерами curl,
    группами доступа, коды ошибок, CORS.
  - [`docs/TELEGRAM.md`](docs/TELEGRAM.md) — BotFather, токен, bind-code
    flow, команды бота, безопасность.
  - `CHANGELOG.md` (этот файл).

## [0.6.6] — 2026-05-12

### Added (INFRA)
- `scripts/deploy.sh` — обновление прод-стенда (fast-forward → pull/build
  → up -d → миграции → prune), с проверкой чистого working tree и
  наличия `.env`.
- Docker `json-file` logging driver на всех сервисах (ротация 10MB × 5),
  лейблы `service` / `environment`.
- Healthchecks для `frontend`, `nginx`, `telegram_bot` в prod-overlay.

### Changed
- `docs/DEPLOY.md` — разделы 10 (логи) и 11 (обновление) переписаны под
  `deploy.sh` и новую log-стратегию.
- `README.md` — упомянут `deploy.sh`.

## [0.6.5] — INFRA: Nginx + HTTPS

### Added
- `docker-compose.prod.yml`, `nginx/nginx.prod.conf`,
  `nginx/templates/default.conf.template`.
- `scripts/init-letsencrypt.sh` — первичный выпуск SSL.
- Certbot-сайдкар, авто-renew каждые 12 ч, nginx reload каждые 6 ч.
- HTTP → HTTPS редирект, HSTS (max-age 2 года).

## [0.6.4] — FE-F: Страница «Настройки»

### Added
- 6 вкладок: Источники / API-ключи / Telegram / Бэкапы / Культуры / Профиль.
- URL-state активной вкладки (`?tab=…`).
- Admin-only гейтинг через `AdminOnlyNotice`.

## [0.6.3] — Эпик ролей и настроек

### Added
- `0.6.3` BE: эндпоинты настроек (`/sources`, `/api-keys`, `/telegram`,
  `/backup`) с Fernet-шифрованием секретов и маскировкой.
- `0.6.3.1` BE: смена пароля авторизованным пользователем.
- `0.6.3.2` BE: admin CRUD для культур (ADR-004).
- `0.6.3.0` BE: роли пользователей (`is_admin`), активность,
  `require_admin` dependency.
- `0.6.3.0.1` BE: инвайт-система (POST/GET/DELETE `/admin/invites` +
  публичные `/auth/invites/{token}` для accept).
- `0.6.3.0.2` BE: admin-эндпоинты управления пользователями
  (`/admin/users`, reset-password).
- `0.6.3.0.3` BE: защита существующих admin-эндпоинтов (`require_admin`
  sweep + role audit).
- `0.6.3.0-FE.1..4` FE: auth store с `/auth/me`, `AdminRoute`, страница
  Accept Invite, Admin Users, создание/отзыв инвайтов.

### Changed (тех. долг 0.6.3.0-DEBT)
- BE: invite URL приведён к path-формату (`/accept-invite/<token>`) —
  ADR-005.
- BE: JWT invalidation через `users.tokens_invalidated_at` (logout/смена
  пароля).
- FE: code-splitting через `React.lazy` + `manualChunks`.

## [0.6.1] — BE: OpenWeatherMap client

### Added
- Клиент текущей погоды + 5d/3h прогноз с агрегированием в суточные.
- `0.6.1.1`: фикс TZ-aware агрегации.

## [0.5.0] — Журнал и отчёты

### Added
- `0.5.0.5` BE: `GET /api/crops` (словарь культур).
- `0.5.1` BE: CRUD событий `field_events` + загрузка фото.
- `0.5.2` BE: снимок погоды в `GET /events/{id}`.
- `0.5.3` BE: сезонные PDF-отчёты (WeasyPrint).
  - `0.5.3.1` BE: `DELETE /api/reports/{file_id}`.
- `0.5.4` FE: страница «Журнал событий» с галереей.
  - fix: `/uploads/` отдаётся nginx-ом статически.
- `0.5.5` FE: страница «Отчёты».

## [0.4.0] — Алерты + Telegram

### Added
- `0.4.1` BE: CRUD правил алертов.
- `0.4.2` BE: движок алертов — ежечасное прогонится + дедуп.
  - `0.4.2.1` fix: TZ-aware datetime в дедупе.
- `0.4.3` BE: Telegram-бот (long-poll, команды, bind-code).
- `0.4.4` BE: уведомления алертов в Telegram (engine→notifier).
  - `0.4.4.0` снимок поля `rule_snapshot` в `alert_history`.
  - `0.4.4.1` `GET /api/alerts/history` с фильтрами и пагинацией.
- `0.4.5` FE: страница «Алерты» — CRUD правил, история, telegram bind.

### Infra
- backend healthcheck, dev port remap для db.

## [0.3.0] — Анализ данных

### Added
- `0.3.1` BE: timeseries chart APIs (`compare_years`, `heatmap`,
  `cumulative`).
- `0.3.2` BE: stats + CSV/XLSX export.
- `0.3.3` BE: climate normals + API + monthly cron recompute.
- `0.3.4` BE: anomalies — отклонения от норм.
- `0.3.5` BE: correlations — Pearson matrix.
- `0.3.6` FE: страница «Графики» (Recharts + Plotly heatmap/corr).
- `0.3.7` FE: страница «Таблицы» (sort/filter/export/presets).
- `0.3.8` FE: страница «Аналитика» — нормы/аномалии/корреляции.

## [0.2.0] — Frontend-каркас

### Added
- `0.2.1` FE: Vite + React + TS + Tailwind + shadcn/ui scaffold.
- `0.2.2` FE: API-клиент + TanStack Query provider.
- `0.2.3` FE: страница логина + auth-store + `ProtectedRoute`.
- `0.2.4` FE: layout + routing + theme toggle.
- `0.2.5` FE: страница «Локации» — CRUD + import progress polling.
- `0.2.6` FE: дашборд — карточки локаций + прогноз + стаб алертов.

## [0.1.0] — Фундамент (MVP-данные)

### Added
- `0.0.1`/`0.0.2` INFRA: project skeleton, base docker-compose, nginx.
- `0.1.1` BE: scaffold FastAPI + `/api/health`.
- `0.1.2` BE: async DB session, Alembic, TimescaleDB extension.
- `0.1.3` BE: модели + миграции + crops-сидер.
- `0.1.4` BE: JWT auth — login/refresh/logout, rate-limit, admin seed.
- `0.1.5` BE: locations CRUD.
- `0.1.6` BE: Open-Meteo (archive + forecast).
- `0.1.7` BE: NASA POWER client.
- `0.1.8` BE: аналитические калькуляторы — VPD, GDD, frost_hours.
- `0.1.9` BE: history backfill при создании локации.
- `0.1.10` BE: универсальный read-эндпоинт `/api/weather/daily`.
- `0.1.11` BE: APScheduler jobs — daily ingest + forecast refresh.

## [0.0.0] — Документация

### Added
- `PRD.md`, `TASKS.md`, `README.md`, `DESIGN-apple.md`,
  `DESIGN-notion.md`, `CLAUDE_PROMPT.md`.

---

[Unreleased]: https://github.com/yourname/weather-agro/compare/v0.6.6...HEAD
[0.6.6]: https://github.com/yourname/weather-agro/releases/tag/v0.6.6
[0.6.5]: https://github.com/yourname/weather-agro/releases/tag/v0.6.5
[0.6.4]: https://github.com/yourname/weather-agro/releases/tag/v0.6.4
[0.6.3]: https://github.com/yourname/weather-agro/releases/tag/v0.6.3
[0.6.1]: https://github.com/yourname/weather-agro/releases/tag/v0.6.1
[0.5.0]: https://github.com/yourname/weather-agro/releases/tag/v0.5.0
[0.4.0]: https://github.com/yourname/weather-agro/releases/tag/v0.4.0
[0.3.0]: https://github.com/yourname/weather-agro/releases/tag/v0.3.0
[0.2.0]: https://github.com/yourname/weather-agro/releases/tag/v0.2.0
[0.1.0]: https://github.com/yourname/weather-agro/releases/tag/v0.1.0
[0.0.0]: https://github.com/yourname/weather-agro/releases/tag/v0.0.0
