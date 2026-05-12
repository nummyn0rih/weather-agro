# Telegram-бот — создание и привязка

Бот — отдельный сервис (`telegram_bot` в docker-compose), переиспользует
backend-образ. Транспорт — long-polling, без webhook → внешние порты ему не
нужны.

## 1. Создание бота через @BotFather

1. В Telegram открыть [@BotFather](https://t.me/BotFather).
2. `/newbot` → задать имя (отображаемое) и **username** (должен оканчиваться
   на `bot`, например `weather_agro_bot`).
3. BotFather пришлёт строку токена вида `123456789:ABCdef...` — это
   `TELEGRAM_BOT_TOKEN`.
4. (По желанию) `/setdescription`, `/setabouttext`, `/setuserpic`.
5. `/setcommands` — вставить список (см. §4 ниже), чтобы Telegram-клиент
   подсказывал команды через `/`.

> Токен — секрет. Утечка = полный контроль над ботом. Утёкший токен
> отзывается через `/revoke` у BotFather.

## 2. Прописать токен

Два пути — переменные в БД (`/api/settings/telegram`) перекрывают `.env`.

### A. Через UI (рекомендуется)
1. Залогиниться под admin → `/settings` → вкладка **«Telegram»**.
2. Вставить токен в поле «Bot token» → «Сохранить».
3. Токен шифруется Fernet (`ENCRYPTION_KEY`), в `GET /api/settings/telegram`
   возвращается замаскированным.

### B. Через `.env` (fallback / первый запуск)
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_BIND_CODE_TTL=300   # секунды, по умолчанию 5 минут
```

### Запустить контейнер

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d telegram_bot

# Проверить, что бот стартанул:
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  logs --tail=50 telegram_bot
# Ожидаемая запись: {"event":"telegram.bot_starting", ...}
```

После смены токена через UI контейнер бота надо рестартануть —
`settings_resolver.get_secret` читается при старте процесса:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  restart telegram_bot
```

## 3. Привязка чата к пользователю

Чтобы бот знал, кто пишет, нужен одноразовый код. Один `telegram_chat_id`
= один пользователь.

### 3.1 Из UI
1. Залогиниться в приложение.
2. `/settings` → вкладка «Telegram» (или раздел «Алерты» — кнопка
   «Подключить Telegram»).
3. Нажать «Сгенерировать код» — появится 6-значный код, действителен
   `TELEGRAM_BIND_CODE_TTL` секунд (по умолчанию 5 мин).
4. В Telegram-клиенте открыть бота, отправить:
   ```
   /start 482917
   ```
5. Бот ответит «✅ Чат привязан к пользователю <username>».

### 3.2 Из API (для скриптов)

```bash
# 1) Выдать код
curl -s -X POST https://<domain>/api/auth/telegram/bind-code \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# → {"code":"482917","expires_at":"2026-05-12T12:00:00Z","bot_username":null}

# 2) Юзер шлёт боту /start <code>
# 3) Проверить статус
curl https://<domain>/api/auth/telegram/status \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# → {"chat_id":123456789,"bound":true}
```

### 3.3 Отвязать

```bash
curl -X DELETE https://<domain>/api/auth/telegram/bind \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```
или кнопка «Отвязать» в UI.

## 4. Команды бота

Точный список — `HELP_TEXT` в `backend/app/telegram_bot/handlers.py`.

| Команда | Что делает |
|---------|------------|
| `/start <код>` | Привязка чата к пользователю (один раз) |
| `/help` | Список команд |
| `/locations` | Список локаций (id, тип, регион) |
| `/weather <id>` | Сводка по последнему доступному дню для локации |
| `/forecast <id>` | Прогноз на 7 дней (среднее по источникам) |
| `/alerts` | Активные правила алертов |
| `/alerts_history` | 10 последних срабатываний |
| `/stats <id> <период>` | Статистика за период (`7d`, `2w`, `3m`, `1y`) |

Все команды кроме `/start` и `/help` требуют привязанного чата.

Строка для `/setcommands` у BotFather:
```
start - Привязать чат: /start <код>
help - Список команд
locations - Список локаций
weather - Погода вчера: /weather <id>
forecast - Прогноз на 7 дней: /forecast <id>
alerts - Активные правила алертов
alerts_history - Последние срабатывания
stats - Статистика: /stats <id> <период>
```

## 5. Push-уведомления (alerts → Telegram)

При срабатывании правила (`scheduler` ежечасно прогоняет движок) и
включённом в правиле `notify_telegram=true` бот шлёт сообщение всем
пользователям с привязанным `telegram_chat_id`, у которых есть доступ к
этой локации.

Если у пользователя `chat_id` не привязан — он молча пропускается; правило
не отключается.

## 6. Безопасность

- **Токен — только в `.env` или зашифрованным в `settings.value`.** Не
  логировать, не передавать в URL-параметрах.
- **Кода привязки одноразовые** и хранятся хеш+TTL в таблице `users`
  (`telegram_bind_code`, `telegram_bind_code_expires_at`). После `/start`
  — обнуляются.
- **`chat_id` уникален** по индексу `users.telegram_chat_id`. Привязать
  один чат к двум юзерам нельзя.
- **Команды бота не выполняют админ-действия** — изменить алерты/локации
  через бота нельзя, только чтение.
- **Webhook не используется** — порт открывать наружу для бота не надо.

## 7. Что делать, если бот молчит

```bash
# Логи (JSON)
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  logs -f telegram_bot

# Частые причины
# - TELEGRAM_BOT_TOKEN пустой → "telegram.token_missing", sys.exit
# - Неверный токен → python-telegram-bot выкинет Unauthorized
# - long-poll стучится в api.telegram.org — проверить исходящий HTTPS с VPS
# - После смены токена в UI забыли перезапустить контейнер бота
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  restart telegram_bot
```

Healthcheck (см. `docker-compose.prod.yml`) проверяет, что процесс
`app.telegram_bot.main` жив — если нет, рестарт по policy `unless-stopped`.

## 8. Связанные документы

- [`docs/API.md`](API.md) §9 — Telegram-эндпоинты.
- [`PRD.md`](../PRD.md) §8 — спецификация бота.
- [`TASKS.md`](../TASKS.md) §4.3 / §4.4 — реализация бота и нотификаций.
