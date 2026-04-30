# Backlog (после MVP)

## Severity для алертов

Добавить поле `severity` (info/warning/critical) в `AlertRule`, UI выбора, snapshot в `AlertHistory.severity_snapshot`, фильтр в API истории.

Контекст: обсуждалось при выполнении задачи 4.4.0, отложено, чтобы не расширять скоуп Этапа 4.

## Test fixture FK gap (severity: low)

Fixture `session_factory` в `backend/tests/test_alert_engine.py:31` использует SQLite с PRAGMA foreign_keys OFF (default) и cherry-picked schema (`Location`, `WeatherDaily`, `AlertHistory` без `AlertRule`). Все существующие engine-тесты передают неперсистентный `AlertRule` объект — FK violation на `alert_history.rule_id` маскируется отключённой PRAGMA.

Также пред-существующие 2 фейла:
- `tests/test_alert_engine.py::test_dedup_blocks_repeat_within_window`
- `tests/test_alert_engine.py::test_dedup_allows_repeat_after_window`

Падают на `engine.py:185` — `TypeError: can't compare offset-naive and offset-aware datetimes`. SQLite возвращает naive datetime при `DateTime(timezone=True)`; на Postgres работает.

DoD-тесты для 4.4.0 живут в отдельном `tests/test_alert_history_fk.py` с собственным fixture (PRAGMA ON, cherry-picked FK-closed subset). Пред-существующая кривизна не трогалась.

**Schema portability:** production-модели используют Postgres-specific server_defaults (`alert_rules.location_ids` с литералом `'[]'::jsonb`). `Base.metadata.create_all` против SQLite падает с `unrecognized token: ":"`. Test-fixtures обязаны cherry-pick'ать FK-closed подмножества и временно стрипать несовместимые `server_default` (см. fixture в `test_alert_history_fk.py`). Также `JSONB`-колонки требуют compile-hook на SQLite (рендер в `JSON`). Long-term fix: testcontainer (real Postgres) или portable defaults в моделях.

Контекст: обнаружено при 4.4.0, отложено как low-priority test infra debt.

## PDF generation blocks event loop

File: backend/app/services/reports/runner.py (BackgroundTasks pattern)
Impact: 1-10s blocking per report; OK for single-tenant MVP
Fix trigger: multi-user mode OR reports routinely >30s
Fix options: run_in_executor (quick) | Celery/RQ (proper)
Added during 5.3.
