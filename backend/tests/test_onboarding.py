from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.models.entities import User, UserProfile

ROOT = "/api/v1"
PASSWORD = "Sample-password-2026"


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def account(kind):
    return {
        "name": f"New {kind}",
        "email": f"{kind.lower()}-{uuid4().hex}@example.com",
        "password": PASSWORD,
        "phone": "555-0100",
        "address": "Test address",
        "date_of_birth": "2000-01-02",
    }


async def sign_in(client, details):
    response = await client.post(
        f"{ROOT}/auth/login", json={"email": details["email"], "password": details["password"]},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_admin_onboards_school_and_principal_can_create_teacher(client, admin_token, db_session):
    principal = account("Principal")
    details = {
        "name": f"Test School {uuid4().hex}",
        "location": "Test campus",
        "state": "Karnataka",
        "infrastructure_tier": "standard",
        "academic_year": "2026-2027",
        "principal": principal,
    }
    assert (await client.post(f"{ROOT}/onboarding/schools", json=details)).status_code == 401
    response = await client.post(f"{ROOT}/onboarding/schools", json=details, headers=headers(admin_token))
    assert response.status_code == 201
    school = response.json()
    login = await sign_in(client, principal)
    assert login["user"]["id"] == school["principal_id"]
    assert login["user"]["role"] == "principal"

    teacher = account("Teacher") | {"designation": "Science teacher"}
    response = await client.post(
        f"{ROOT}/onboarding/teachers", json=teacher, headers=headers(login["access_token"]),
    )
    assert response.status_code == 201
    teacher_login = await sign_in(client, teacher)
    assert teacher_login["user"]["role"] == "teacher"
    assert teacher_login["user"]["school_id"] == school["id"]
    profile = await db_session.get(UserProfile, teacher_login["user"]["id"])
    assert (profile.phone, profile.address, profile.date_of_birth.isoformat()) == (
        teacher["phone"], teacher["address"], teacher["date_of_birth"],
    )
    assert (await client.post(
        f"{ROOT}/onboarding/teachers", json=account("Other teacher"),
        headers=headers(teacher_login["access_token"]),
    )).status_code == 403


@pytest.mark.asyncio
async def test_student_credentials_are_required_and_resolve_the_new_roster_record(
    client, teacher_token, db_session,
):
    details = account("Student") | {"class_id": "class-8a", "roll_no": 2000}
    response = await client.post(f"{ROOT}/onboarding/students", json=details, headers=headers(teacher_token))
    assert response.status_code == 201
    user = await db_session.get(User, response.json()["id"])
    assert user.hashed_password.startswith("$2")
    assert "hashed_password" not in response.json()

    for email, password in [(details["email"], "wrong"), (details["email"], "demo123"),
                            ("missing@example.com", PASSWORD)]:
        response = await client.post(f"{ROOT}/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401

    login = await sign_in(client, details)
    response = await client.get(f"{ROOT}/classes/students/me", headers=headers(login["access_token"]))
    assert response.status_code == 200
    assert response.json()["name"] == details["name"]
    assert response.json()["roll_no"] == details["roll_no"]

    duplicate = account("Duplicate") | {"class_id": details["class_id"], "roll_no": details["roll_no"]}
    response = await client.post(f"{ROOT}/onboarding/students", json=duplicate, headers=headers(teacher_token))
    assert response.status_code == 409
    assert await db_session.scalar(select(User.id).where(User.email == duplicate["email"])) is None

    response = await client.post(
        f"{ROOT}/onboarding/students", json=duplicate | {"class_id": "class-pragati-8"},
        headers=headers(teacher_token),
    )
    assert response.status_code == 404
