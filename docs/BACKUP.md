# Бэкапы — Яндекс.Диск (WebDAV)

Документ описывает, как настроить автоматические бэкапы БД и как
восстановить данные из дампа.

## Текущий статус

- ✅ **Хранилище секретов** — поля `yandex_disk_login`, `yandex_disk_app_password`,
  `yandex_disk_path` сохраняются через `PUT /api/settings/backup`. Пароль
  шифруется Fernet (`ENCRYPTION_KEY`), маскируется в `GET`.
- ✅ **UI** — вкладка «Бэкапы» на странице `/settings` (admin-only).
- ⏳ **Runner / scheduler / `POST /api/backup/run` / `GET /api/backup/list` /
  `scripts/restore.py`** — задача 6.2, ещё не реализована. Кнопка «Сделать
  бэкап сейчас» в UI отключена до её закрытия.

Этот документ покрывает **обе** части: что уже работает (настройка) и что
появится после 6.2 (расписание, restore). Изменения там — мелкие правки
внутри этого файла, не нужно переписывать целиком.

---

## 1. Учётная запись Яндекс.Диск

1. Авторизуйся под учёткой, на которую будут идти бэкапы:
   <https://passport.yandex.ru/profile>.
2. Раздел «**Пароли приложений**» → «**Создать новый пароль**».
3. Тип — «**Файлы (WebDAV)**».
4. Сохрани пароль (показывается **один раз**, без пробелов).

WebDAV endpoint Яндекс.Диска — `https://webdav.yandex.ru` (не настраивается).

## 2. Заполнить настройки в приложении

Два пути — эквивалентны, переменные в БД перекрывают `.env`:

### A. Через UI (рекомендуется)
1. Залогиниться под admin → `/settings` → вкладка **«Бэкапы»**.
2. Поля:
   - **Login Яндекс.Диска** — email/логин без `@yandex.ru` тоже годится.
   - **App password** — пароль приложения из шага 1.
   - **Папка на Диске** — например `/weather-app-backups/` (создаётся
     автоматически).
3. «Сохранить». Пароль будет зашифрован в БД.

### B. Через `.env` (fallback / первый старт)
```env
YANDEX_DISK_LOGIN=ivan.ivanov
YANDEX_DISK_APP_PASSWORD=appspecificpassword
YANDEX_DISK_BACKUP_PATH=/weather-app-backups/
BACKUP_RETENTION_DAILY=30
BACKUP_RETENTION_MONTHLY=12
```

Перезапуск backend после правки `.env`:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
```

## 3. Расписание (задача 6.2 — TODO)

Согласно PRD §9.1, после реализации 6.2:

| Cron (MSK) | Действие |
|------------|----------|
| `0 4 * * *` | `pg_dump weather` → gzip → `WEBDAV/${YANDEX_DISK_BACKUP_PATH}weather-YYYYMMDD.sql.gz` |
| при загрузке | Ротация: дневные старше `BACKUP_RETENTION_DAILY` дней удаляются, помесячный снепшот за каждый месяц хранится `BACKUP_RETENTION_MONTHLY` месяцев |

Логи запусков — в таблице `backup_logs` (`status`, `size_bytes`, `error`,
`started_at`, `finished_at`).

Переопределение расписания — `BACKUP_CRON` в `.env` (формат APScheduler
cron — см. `app/scheduler/jobs.py`).

## 4. Ручной запуск (задача 6.2 — TODO)

После 6.2 будут доступны:
```bash
# REST (admin token)
curl -X POST https://<domain>/api/backup/run \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# UI: /settings → «Бэкапы» → «Сделать бэкап сейчас»

# CLI
docker compose exec backend python -m app.scripts.backup
```

Возвращает `{file: "weather-20260512.sql.gz", size_bytes: 12345678}`.

## 5. Восстановление

### 5.1 Скачать дамп с Яндекс.Диска

Любым WebDAV-клиентом (`cadaver`, mountpoint, веб-интерфейс Диска).
Пример curl:
```bash
curl -u "${YANDEX_DISK_LOGIN}:${YANDEX_DISK_APP_PASSWORD}" \
  -o weather-20260512.sql.gz \
  "https://webdav.yandex.ru/${YANDEX_DISK_BACKUP_PATH}weather-20260512.sql.gz"
```

Или через UI после 6.2 (`GET /api/backup/list` + download link).

### 5.2 Восстановить в работающий стенд

> ⚠️ Восстановление **удаляет текущие данные**. Сначала останови приложение,
> чтобы backend не писал в БД во время restore.

```bash
# 1. Остановить backend и scheduler (db оставляем):
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop backend telegram_bot

# 2. Положить дамп рядом с docker-compose
ls weather-20260512.sql.gz

# 3. Скрипт восстановления (задача 6.2):
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  python -m app.scripts.restore weather-20260512.sql.gz

# Эквивалент руками — пока скрипта нет:
gunzip -c weather-20260512.sql.gz \
  | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
    psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

# 4. Применить миграции (на случай если дамп старее текущего кода):
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  alembic upgrade head

# 5. Поднять обратно:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend telegram_bot
```

### 5.3 Восстановление в чистое окружение

Полезно для disaster recovery или прогона дампа на dev-машине:

```bash
git clone <repo> && cd weather-agro
cp .env.example .env && nano .env   # минимум POSTGRES_*, SECRET_KEY, ENCRYPTION_KEY
docker compose -f docker-compose.dev.yml up -d db
# дождаться healthy
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head

gunzip -c weather-20260512.sql.gz \
  | docker compose -f docker-compose.dev.yml exec -T db \
    psql -U weather -d weather

docker compose -f docker-compose.dev.yml up -d
```

> **`ENCRYPTION_KEY` критичен.** Если ключ не совпадает с тем, что был при
> создании дампа, зашифрованные строки в `settings.value` (Telegram-токен,
> Яндекс-пароль, OpenWeatherMap-ключ) расшифровать не удастся. Храни ключ
> отдельно от дампов (а лучше — в менеджере паролей).

## 6. Проверка работоспособности

После настройки и (когда появится) первого запуска:

```bash
# Свежий дамп на Диске
curl -u "${YANDEX_DISK_LOGIN}:${YANDEX_DISK_APP_PASSWORD}" \
  -X PROPFIND -H "Depth: 1" \
  "https://webdav.yandex.ru/${YANDEX_DISK_BACKUP_PATH}" \
  | xmllint --format -

# Размер базы (для прикидки времени бэкапа)
docker compose exec db \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -c "SELECT pg_size_pretty(pg_database_size('${POSTGRES_DB}'));"

# Логи последнего бэкапа (после 6.2)
docker compose exec backend \
  python -c "from app.db.session import sync; \
             [print(r) for r in sync.execute('SELECT * FROM backup_logs ORDER BY id DESC LIMIT 5').all()]"
```

## 7. Безопасность

- **Не коммитить `.env`** — `app_password` Яндекс.Диска даёт доступ только
  к WebDAV, но получить через него весь дамп БД достаточно.
- **WebDAV `app_password` можно отозвать** в любой момент через
  passport.yandex.ru → «Пароли приложений» → корзина.
- **Дамп содержит хеши паролей и зашифрованные секреты** — обращаться с ним
  как с production-БД.
- **`ENCRYPTION_KEY` не лежит на Диске.** Если потерять и его, и backend —
  расшифровать секреты в `settings.value` невозможно.
- **HTTPS обязателен.** Прод-конфиг (`docker-compose.prod.yml`) кладёт
  WebDAV-обращения за `httpx` с TLS-проверкой — нестандартный CA не
  настраивать без необходимости.

## 8. Связанные документы

- [`PRD.md`](../PRD.md) §10 — общая стратегия бэкапов.
- [`TASKS.md`](../TASKS.md) §6.2 — DoD реализации.
- [`docs/DECISIONS.md`](DECISIONS.md) ADR-002 — почему оставили WebDAV
  `login + app_password` вместо OAuth.
- [`docs/DEPLOY.md`](DEPLOY.md) — про `.env` и production-стек.
