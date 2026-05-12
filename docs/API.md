# API — обзор и типовые сценарии

Полный, всегда актуальный референс — **Swagger UI**:

| Окружение | URL |
|-----------|-----|
| Dev       | <http://localhost:8000/api/docs> |
| Prod      | `https://<DOMAIN>/api/docs` |
| ReDoc     | `<base>/api/redoc` |
| OpenAPI JSON | `<base>/api/openapi.json` |

Все эндпоинты префиксованы `/api`. Все JSON-ответы — `application/json; charset=utf-8`.

---

## 1. Аутентификация

JWT (`HS256`) — два токена: `access` (15 мин) и `refresh` (7 дней). Все
защищённые эндпоинты ждут `Authorization: Bearer <access_token>`.

Группы:
- **Анонимные:** `/api/health`, `/api/auth/login`, `/api/auth/refresh`,
  `/api/auth/invites/{token}` (GET/POST accept).
- **User:** всё кроме `/admin/*` и admin-only групп.
- **Admin (`is_admin=true`):** `/api/admin/*`, `/api/crops` (POST/PUT/DELETE),
  `/api/settings/*` (PUT), `/api/locations` (POST/PUT/DELETE).

Подробно — [`docs/endpoint-roles.md`](endpoint-roles.md).

### 1.1 Логин и refresh

```bash
# Логин
curl -s -X POST https://<domain>/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"changeme"}'
# → {"access_token":"...","refresh_token":"..."}

# Запрос с access-токеном
curl -s https://<domain>/api/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# → {"id":1,"username":"admin","is_admin":true,...}

# Refresh
curl -s -X POST https://<domain>/api/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
# → новый access + refresh
```

### 1.2 Logout + invalidation

`POST /api/auth/logout` помечает `tokens_invalidated_at = now()` на
пользователе — все ранее выданные токены становятся невалидны (ADR
`6.3.0-DEBT.2`).

### 1.3 Смена пароля
```bash
curl -X POST https://<domain>/api/auth/change-password \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"old","new_password":"newPass1!"}'
```

### 1.4 Инвайты (admin создаёт, юзер принимает)
```bash
# Admin создаёт инвайт
curl -X POST https://<domain>/api/admin/invites \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"role":"user","ttl_hours":48}'
# → {"invite_url":"https://<domain>/accept-invite/<token>",...}

# Гость открывает GET /accept-invite/<token> в UI,
# фронт зовёт POST /api/auth/invites/<token>/accept с {username,password}.
```

---

## 2. Локации

```bash
# Список
curl -H "Authorization: Bearer $T" https://<domain>/api/locations

# Создание — запускает фоновый history backfill (10 лет)
curl -X POST https://<domain>/api/locations \
  -H "Authorization: Bearer $T" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Поле №1","type":"growing","region":"MO",
       "latitude":55.7,"longitude":37.6}'

# Прогресс импорта (polling)
curl -H "Authorization: Bearer $T" \
  https://<domain>/api/locations/1/import-status
# → {"status":"running","import_progress":0.42,...}
```

---

## 3. Погода

Универсальный эндпоинт чтения — `GET /api/weather/daily`. Источник
выбирается параметром `source ∈ {open_meteo, nasa_power, openweathermap, average}`.

```bash
# Суточные данные, среднее по источникам
curl -G https://<domain>/api/weather/daily \
  -H "Authorization: Bearer $T" \
  --data-urlencode "location_id=1" \
  --data-urlencode "start=2025-05-01" \
  --data-urlencode "end=2025-05-31" \
  --data-urlencode "source=average"

# Heatmap (год × день года, для одной локации)
curl -G https://<domain>/api/weather/heatmap \
  -H "Authorization: Bearer $T" \
  --data-urlencode "location_id=1" \
  --data-urlencode "parameter=temp_avg" \
  --data-urlencode "year_from=2020" \
  --data-urlencode "year_to=2025"

# Накопительная сумма (например, GDD)
curl -G https://<domain>/api/weather/cumulative \
  -H "Authorization: Bearer $T" \
  --data-urlencode "location_id=1" \
  --data-urlencode "parameter=gdd" \
  --data-urlencode "crop_id=2" \
  --data-urlencode "year=2025"

# Сводные статистики
curl -G https://<domain>/api/weather/stats ...

# Экспорт в CSV/XLSX
curl -G "https://<domain>/api/weather/export?format=csv&..." \
  -H "Authorization: Bearer $T" -o weather.csv
```

---

## 4. Аналитика

```bash
# Climate normals (1991-2020 baseline по умолчанию)
curl -G https://<domain>/api/analytics/normals \
  -H "Authorization: Bearer $T" \
  --data-urlencode "location_id=1" \
  --data-urlencode "parameter=temp_avg"

# Аномалии — отклонение от нормы
curl -G https://<domain>/api/analytics/anomalies ...

# Корреляции — Пирсон между параметрами
curl -G https://<domain>/api/analytics/correlations ...
```

---

## 5. Алерты

```bash
# Список правил
curl -H "Authorization: Bearer $T" https://<domain>/api/alerts/rules

# Создать правило
curl -X POST https://<domain>/api/alerts/rules \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"name":"Заморозки","location_id":1,
       "parameter":"temp_min","condition":"lt","threshold":0,
       "enabled":true,"notify_telegram":true}'

# История срабатываний (с фильтрами/пагинацией)
curl -G https://<domain>/api/alerts/history \
  -H "Authorization: Bearer $T" \
  --data-urlencode "location_id=1" \
  --data-urlencode "limit=50"
```

Движок прогоняется ежечасно (`scheduler/jobs.py`). Дедупликация — по
`(rule_id, location_id, день)`.

---

## 6. Журнал событий

```bash
# Список (фильтры: location_id, crop_id, type, from, to)
curl -G https://<domain>/api/events -H "Authorization: Bearer $T"

# Создать событие
curl -X POST https://<domain>/api/events \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"date":"2025-05-15","location_id":1,"crop_id":2,
       "type":"planting","note":"Высадили 3 ряда"}'

# Снимок погоды на дату события
curl -H "Authorization: Bearer $T" https://<domain>/api/events/42

# Загрузить фото (multipart, до MAX_PHOTOS_PER_EVENT штук)
curl -X POST https://<domain>/api/events/42/photos \
  -H "Authorization: Bearer $T" \
  -F "files=@field.jpg"
# Фото отдаются nginx-ом из /uploads/ — путь возвращается в ответе.
```

---

## 7. Отчёты (PDF)

```bash
# Запуск генерации (синхронная — может занять 10-30 сек)
curl -X POST https://<domain>/api/reports/generate \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"location_id":1,"year":2025,"crop_id":2}'
# → {"file_id":17,"filename":"report-2025-loc1.pdf",...}

# Список
curl -H "Authorization: Bearer $T" https://<domain>/api/reports

# Скачать
curl -OJ -H "Authorization: Bearer $T" \
  https://<domain>/api/reports/17/download
```

---

## 8. Настройки (admin)

Группы: `sources`, `api-keys`, `telegram`, `backup`. Секреты (Telegram-токен,
OWM-ключ, Яндекс app_password) шифруются Fernet перед записью, маскируются
при чтении (`***last4`).

```bash
# Получить (пароли замаскированы)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://<domain>/api/settings/api-keys

# Обновить (пустая строка = очистить поле; null = не трогать)
curl -X PUT https://<domain>/api/settings/api-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"openweathermap_api_key":"new-secret-key"}'
```

См. [`docs/DECISIONS.md`](DECISIONS.md) ADR-002 для детальной модели.

---

## 9. Telegram

См. [`docs/TELEGRAM.md`](TELEGRAM.md). Кратко:

```bash
# Выдать одноразовый bind-код
curl -X POST https://<domain>/api/auth/telegram/bind-code \
  -H "Authorization: Bearer $T"
# → {"code":"482917","expires_at":"...","bot_username":null}
# Юзер шлёт боту /start 482917 — chat_id привязывается к юзеру.

# Статус привязки
curl https://<domain>/api/auth/telegram/status \
  -H "Authorization: Bearer $T"

# Отвязать
curl -X DELETE https://<domain>/api/auth/telegram/bind \
  -H "Authorization: Bearer $T"
```

---

## 10. Health и наблюдаемость

```bash
# Health (без авторизации) — используется nginx и docker healthcheck
curl https://<domain>/api/health
# → {"status":"ok","db":"ok","version":"..."}

# Метрики rate-limit видны в заголовках `X-RateLimit-*` на /api/auth/login.
```

---

## 11. Коды ошибок

| HTTP | Когда |
|------|-------|
| 400 | Невалидный payload (Pydantic) |
| 401 | Нет/просрочен/инвалидирован токен |
| 403 | Юзер не имеет роли (например, не admin) или попытка тронуть чужой ресурс |
| 404 | Сущность отсутствует |
| 409 | Конфликт (повторный username, повторный invite-token, race-condition в backfill) |
| 422 | Pydantic-валидация — детальный body в `.detail[]` |
| 429 | Rate limit (`/auth/login`: 5 попыток/мин/IP) |
| 5xx | Лог в `docker compose logs backend` |

Тело ошибки — стандартный FastAPI:
```json
{"detail": "Описание" }            // или
{"detail": [{"loc":[...],"msg":"...","type":"..."}]}
```

---

## 12. CORS

Список разрешённых origin задаётся `CORS_ORIGINS` (запятыми). В production
обычно один — сам `https://<DOMAIN>`. Любой другой Origin получит 403 на
preflight.

---

## 13. Версии и breaking changes

Изменения API фиксируются в [`CHANGELOG.md`](../CHANGELOG.md). Сейчас
проект до 1.0 — версия не пинуется в URL, ломать совместимость
допустимо между minor-вехами MVP.
