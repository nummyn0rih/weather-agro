#!/usr/bin/env bash
# Обновление прод-стенда.
#
# Что делает:
#   1. git fetch + fast-forward до origin/<branch> (по умолчанию main).
#   2. Сборка образов backend/frontend и подтяжка внешних (db/nginx/certbot).
#   3. Применение alembic-миграций.
#   4. Перезапуск стека.
#   5. Очистка висящих образов.
#
# Использование:
#   ./scripts/deploy.sh                # ветка main
#   ./scripts/deploy.sh release/v1.2   # другая ветка/тег
#
# Безопасность:
#   - Скрипт отказывается работать при незакоммиченных изменениях в репо.
#   - Все переменные читаются из .env (не передавать секреты через CLI).
#   - --pull для внешних образов, --build для собственных — кэш Docker
#     слоёв ускоряет инкрементальные апдейты.

set -euo pipefail

BRANCH="${1:-main}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${PROJECT_ROOT}"

echo ">>> [1/6] Проверка состояния репозитория..."
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: рабочее дерево не чистое. Закоммить/спрячь изменения." >&2
  git status --short >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: нет .env в ${PROJECT_ROOT}. Скопируй из .env.example." >&2
  exit 1
fi

echo ">>> [2/6] git fetch + fast-forward до origin/${BRANCH}..."
git fetch --prune origin
git checkout "${BRANCH}"
git merge --ff-only "origin/${BRANCH}"

echo ">>> [3/6] Подтяжка внешних образов (db/nginx/certbot)..."
$COMPOSE pull --ignore-pull-failures db nginx certbot

echo ">>> [4/6] Сборка backend/frontend..."
$COMPOSE build --pull backend frontend

echo ">>> [5/6] Запуск стека (миграции применяются ниже, после старта db)..."
$COMPOSE up -d --remove-orphans

echo ">>> ... ожидание healthy db ..."
# Wait до 60 секунд: пока db не станет healthy, миграция бесполезна.
for i in $(seq 1 30); do
  if $COMPOSE ps db | grep -q "(healthy)"; then
    break
  fi
  sleep 2
done

echo ">>> ... alembic upgrade head ..."
$COMPOSE exec -T backend alembic upgrade head

echo ">>> [6/6] Очистка висящих образов..."
docker image prune -f

echo ""
echo ">>> Готово. Состояние:"
$COMPOSE ps
echo ""
echo ">>> Версия:  $(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))"
