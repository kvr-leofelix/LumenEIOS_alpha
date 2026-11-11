import hashlib

import pytest
from pydantic import SecretStr

from backend.app.core.config import settings
from backend.app.core.security import verify_password


def test_existing_sha256_password_hash_can_still_be_verified():
    stored = hashlib.sha256(b"demo123").hexdigest()
    assert verify_password("demo123", stored)
    assert not verify_password("wrong", stored)


@pytest.mark.asyncio
async def test_demo_root_switches_roles_and_requires_development_opt_in(client, teacher_token, monkeypatch):
    url = "/api/v1/auth"
    password = "example-dev-test-password"
    credentials = {"email": "LEOFELIX", "password": password}
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "DEMO_ROOT_PASSWORD", None)
    assert (await client.post(f"{url}/login", json=credentials)).status_code == 401
    monkeypatch.setattr(settings, "DEMO_ROOT_PASSWORD", SecretStr(password))
    assert (await client.post(f"{url}/login", json=credentials | {"password": "wrong"})).status_code == 401
    assert (await client.post(
        f"{url}/demo-root/role", json={"role": "admin"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )).status_code == 403

    response = await client.post(f"{url}/login", json=credentials)
    assert response.status_code == 200
    session = response.json()
    assert session["user"]["role"] == "developer"
    assert session["user"]["demo_root"] is True
    assert (await client.get(
        f"{url}/me", headers={"Authorization": f"Bearer {session['access_token']}"}
    )).json()["role"] == "developer"
    email_login = await client.post(
        f"{url}/login", json={"email": "leofelix@lumeneios.demo", "password": password}
    )
    assert email_login.status_code == 200
    assert email_login.json()["user"]["role"] == "developer"
    assert email_login.json()["user"]["demo_root"] is True
    for role in ("principal", "teacher", "student", "parent", "admin", "developer"):
        response = await client.post(
            f"{url}/demo-root/role", json={"role": role},
            headers={"Authorization": f"Bearer {session['access_token']}"},
        )
        assert response.status_code == 200
        session = response.json()
        assert session["user"]["role"] == role
        assert session["user"]["demo_root"] is True

    headers = {"Authorization": f"Bearer {session['access_token']}"}
    assert (await client.get(f"{url}/me", headers=headers)).json()["demo_root"] is True
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert (await client.get(f"{url}/me", headers=headers)).status_code == 401
    assert (await client.post(f"{url}/login", json=credentials)).status_code == 401
