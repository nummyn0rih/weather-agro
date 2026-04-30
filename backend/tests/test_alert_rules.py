from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.models import AlertRule, User
from app.db.session import get_db
from app.main import app
from app.services.alerts import rules as rules_service

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_rule(
    id_: int = 1,
    name: str = "Heat",
    parameter: str = "temperature_max",
    condition: str = "gt",
    threshold: float = 35.0,
    threshold_max: float | None = None,
    enabled: bool = True,
) -> AlertRule:
    return AlertRule(
        id=id_,
        name=name,
        parameter=parameter,
        condition=condition,
        threshold=threshold,
        threshold_max=threshold_max,
        location_ids=[],
        enabled=enabled,
        telegram=True,
        created_at=_NOW,
    )


@pytest.fixture
def client(monkeypatch):
    store: dict[int, AlertRule] = {1: _make_rule()}

    async def fake_list(_session, enabled=None):
        items = list(store.values())
        if enabled is not None:
            items = [r for r in items if r.enabled == enabled]
        return items

    async def fake_get(_session, rid):
        return store.get(rid)

    async def fake_create(_session, data):
        new_id = max(store.keys(), default=0) + 1
        rule = AlertRule(id=new_id, created_at=_NOW, **data.model_dump())
        store[new_id] = rule
        return rule

    async def fake_update(_session, rid, data):
        if rid not in store:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(store[rid], k, v)
        return store[rid]

    async def fake_delete(_session, rid):
        return store.pop(rid, None) is not None

    monkeypatch.setattr(rules_service, "list_rules", fake_list)
    monkeypatch.setattr(rules_service, "get_rule", fake_get)
    monkeypatch.setattr(rules_service, "create_rule", fake_create)
    monkeypatch.setattr(rules_service, "update_rule", fake_update)
    monkeypatch.setattr(rules_service, "delete_rule", fake_delete)

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_list_rules(client) -> None:
    response = client.get("/api/alerts/rules")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Heat"
    assert body[0]["condition"] == "gt"


def test_list_filter_enabled(client) -> None:
    assert len(client.get("/api/alerts/rules?enabled=true").json()) == 1
    assert len(client.get("/api/alerts/rules?enabled=false").json()) == 0


def test_get_rule(client) -> None:
    response = client.get("/api/alerts/rules/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_rule_404(client) -> None:
    assert client.get("/api/alerts/rules/999").status_code == 404


def test_create_rule(client) -> None:
    response = client.post(
        "/api/alerts/rules",
        json={
            "name": "Frost",
            "parameter": "temperature_min",
            "condition": "lt",
            "threshold": -5.0,
            "location_ids": [1, 2],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Frost"
    assert body["condition"] == "lt"
    assert body["threshold"] == -5.0
    assert body["location_ids"] == [1, 2]
    assert body["enabled"] is True


def test_create_between_requires_threshold_max(client) -> None:
    response = client.post(
        "/api/alerts/rules",
        json={
            "name": "Comfort",
            "parameter": "temperature_avg",
            "condition": "between",
            "threshold": 18.0,
        },
    )
    assert response.status_code == 422


def test_create_between_threshold_order(client) -> None:
    response = client.post(
        "/api/alerts/rules",
        json={
            "name": "Bad",
            "parameter": "temperature_avg",
            "condition": "between",
            "threshold": 30.0,
            "threshold_max": 20.0,
        },
    )
    assert response.status_code == 422


def test_create_between_ok(client) -> None:
    response = client.post(
        "/api/alerts/rules",
        json={
            "name": "Comfort",
            "parameter": "temperature_avg",
            "condition": "between",
            "threshold": 18.0,
            "threshold_max": 26.0,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["threshold_max"] == 26.0


def test_update_partial(client) -> None:
    response = client.put(
        "/api/alerts/rules/1", json={"enabled": False, "threshold": 40.0}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["threshold"] == 40.0
    assert body["name"] == "Heat"


def test_update_invalid_between_via_partial(client) -> None:
    response = client.put(
        "/api/alerts/rules/1", json={"condition": "between"}
    )
    assert response.status_code == 422


def test_update_404(client) -> None:
    assert (
        client.put("/api/alerts/rules/999", json={"enabled": False}).status_code == 404
    )


def test_delete(client) -> None:
    response = client.delete("/api/alerts/rules/1")
    assert response.status_code == 204
    assert client.get("/api/alerts/rules/1").status_code == 404


def test_delete_404(client) -> None:
    assert client.delete("/api/alerts/rules/999").status_code == 404


def test_create_invalid_parameter(client) -> None:
    response = client.post(
        "/api/alerts/rules",
        json={
            "name": "Bad",
            "parameter": "bogus",
            "condition": "gt",
            "threshold": 1.0,
        },
    )
    assert response.status_code == 422
