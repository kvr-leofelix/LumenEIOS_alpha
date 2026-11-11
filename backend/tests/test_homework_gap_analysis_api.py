"""Tests for GET /api/v1/students/{student_id}/homework/gap-analysis."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models.entities import (
    AuditEvent,
    HomeworkRemediation,
    Notification,
    ParentStudentLink,
    SchoolMembership,
    Student,
    StudentCompetencySnapshot,
    User,
)

URL = "/api/v1/students/{}/homework/gap-analysis"


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def make_student(school_id, class_id, lu=48, cu=74, au=62, ct=50):
    return Student(
        id=uid("gapapi-student"),
        school_id=school_id,
        class_id=class_id,
        class_name="Test Class",
        name="Private Test Name",
        roll_no=900,
        lu_score=lu, cu_score=cu, au_score=au, ct_score=ct, overall_score=59,
        baseline_lu=60, baseline_cu=80, baseline_au=50, baseline_ct=50, baseline_overall=60,
    )


def make_user(role, school_id):
    user_id = uid(f"gapapi-{role}")
    return User(
        id=user_id,
        email=f"{user_id}@test.invalid",
        name=f"Test {role}",
        hashed_password="not-used",
        role=role,
        school_id=school_id,
    )


def bearer(user_id, school_id, role):
    return {"Authorization": f"Bearer {create_access_token(user_id, school_id=school_id, role=role)}"}


@pytest_asyncio.fixture
async def world(db_session):
    """Students, users and relationships created for one test, then removed."""
    s1 = make_student("school-1", "class-8a")
    s3 = make_student("school-3", "class-pragati-8", lu=80, cu=40, au=60, ct=70)
    bad = make_student("school-1", "class-8a", lu=150)

    linked_parent = make_user("parent", "school-1")
    unrelated_parent = make_user("parent", "school-1")
    member_teacher = make_user("teacher", "school-3")
    lapsed_teacher = make_user("teacher", "school-3")

    link = ParentStudentLink(id=uid("gapapi-link"), parent_user_id=linked_parent.id, student_id=s1.id)
    active = SchoolMembership(id=uid("gapapi-mem"), user_id=member_teacher.id, school_id="school-1",
                              role="teacher", is_active=True)
    inactive = SchoolMembership(id=uid("gapapi-mem"), user_id=lapsed_teacher.id, school_id="school-1",
                                role="teacher", is_active=False)

    rows = [s1, s3, bad, linked_parent, unrelated_parent, member_teacher, lapsed_teacher, link, active, inactive]
    db_session.add_all(rows)
    await db_session.commit()

    yield {
        "s1": s1, "s3": s3, "bad": bad,
        "linked_parent": linked_parent, "unrelated_parent": unrelated_parent,
        "member_teacher": member_teacher, "lapsed_teacher": lapsed_teacher,
    }

    for row in [link, active, inactive, s1, s3, bad, linked_parent, unrelated_parent, member_teacher, lapsed_teacher]:
        await db_session.delete(row)
    await db_session.commit()


# --- Allowed ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_teacher_in_same_school_gets_analysis(client, teacher_token, world):
    res = await client.get(URL.format(world["s1"].id), headers={"Authorization": f"Bearer {teacher_token}"})

    assert res.status_code == 200
    body = res.json()
    assert body["student_id"] == world["s1"].id
    assert body["weakest"] == ["LU"]
    assert [g["competency"] for g in body["ranked"]] == ["LU", "CT", "AU", "CU"]
    assert body["source"] == "student_live_scores"


@pytest.mark.asyncio
async def test_response_has_fixed_schema_and_no_personal_details(client, teacher_token, world):
    res = await client.get(URL.format(world["s1"].id), headers={"Authorization": f"Bearer {teacher_token}"})
    body = res.json()

    assert set(body) == {
        "student_id", "ranked", "weakest", "has_single_weakest", "lowest_score",
        "highest_score", "spread", "source", "notes",
    }
    assert set(body["ranked"][0]) == {"competency", "score", "rank", "baseline", "change_from_baseline"}
    assert "Private Test Name" not in res.text
    assert "school" not in res.text


@pytest.mark.asyncio
async def test_principal_in_same_school_gets_analysis(client, principal_token, world):
    res = await client.get(URL.format(world["s1"].id), headers={"Authorization": f"Bearer {principal_token}"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_view_any_school(client, admin_token, world):
    res = await client.get(URL.format(world["s3"].id), headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["weakest"] == ["CU"]


@pytest.mark.asyncio
async def test_teacher_with_active_membership_in_other_school_is_allowed(client, world):
    t = world["member_teacher"]
    res = await client.get(URL.format(world["s1"].id), headers=bearer(t.id, t.school_id, "teacher"))
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_linked_parent_gets_analysis(client, world):
    p = world["linked_parent"]
    res = await client.get(URL.format(world["s1"].id), headers=bearer(p.id, p.school_id, "parent"))
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_seeded_parent_link_is_honoured(client, parent_token):
    # Seed data links user-parent-1 to student-ananya through ParentStudentLink.
    res = await client.get(URL.format("student-ananya"), headers={"Authorization": f"Bearer {parent_token}"})
    assert res.status_code == 200


# --- Denied -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_teacher_from_other_school_is_denied(client, other_school_teacher_token, world):
    res = await client.get(URL.format(world["s1"].id),
                           headers={"Authorization": f"Bearer {other_school_teacher_token}"})
    assert res.status_code == 403
    assert "LU" not in res.text


@pytest.mark.asyncio
async def test_inactive_membership_is_denied(client, world):
    t = world["lapsed_teacher"]
    res = await client.get(URL.format(world["s1"].id), headers=bearer(t.id, t.school_id, "teacher"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unrelated_parent_is_denied(client, world):
    p = world["unrelated_parent"]
    res = await client.get(URL.format(world["s1"].id), headers=bearer(p.id, p.school_id, "parent"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_parent_cannot_see_unlinked_student_in_same_school(client, parent_token, world):
    res = await client.get(URL.format(world["s1"].id), headers={"Authorization": f"Bearer {parent_token}"})
    assert res.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["user-student-1", "other", "no-such-student"])
async def test_students_are_denied_including_their_own_record(client, student_token, world, target):
    # user-student-1 shares its ID with a Student row, but that isn't an approved identity link.
    student_id = world["s1"].id if target == "other" else target
    res = await client.get(URL.format(student_id), headers={"Authorization": f"Bearer {student_token}"})
    assert res.status_code == 403  # also 403 for unknown IDs, so students can't probe which exist


@pytest.mark.asyncio
async def test_missing_token_is_rejected_when_demo_mode_is_off(client, world):
    previous = settings.DEMO_MODE
    settings.DEMO_MODE = False
    try:
        res = await client.get(URL.format(world["s1"].id))
        assert res.status_code == 401
    finally:
        settings.DEMO_MODE = previous


# --- Errors -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_student_returns_404(client, teacher_token):
    res = await client.get(URL.format("no-such-student"), headers={"Authorization": f"Bearer {teacher_token}"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_invalid_stored_scores_return_safe_error(client, teacher_token, world):
    res = await client.get(URL.format(world["bad"].id), headers={"Authorization": f"Bearer {teacher_token}"})

    assert res.status_code == 500
    assert res.json() == {"detail": "This student's competency data is invalid. Contact an administrator."}
    assert "150" not in res.text


@pytest.mark.asyncio
async def test_invalid_scores_are_not_revealed_to_unauthorized_users(client, other_school_teacher_token, world):
    # Access is checked before scores are read, so an outsider gets 403, not the data error.
    res = await client.get(URL.format(world["bad"].id),
                           headers={"Authorization": f"Bearer {other_school_teacher_token}"})
    assert res.status_code == 403


# --- Read-only ----------------------------------------------------------------------


async def table_counts(db):
    counts = {}
    for model in (Student, StudentCompetencySnapshot, AuditEvent, HomeworkRemediation, Notification):
        counts[model.__tablename__] = await db.scalar(select(func.count()).select_from(model))
    return counts


@pytest.mark.asyncio
async def test_endpoint_writes_nothing(client, db_session, teacher_token, other_school_teacher_token, world):
    s1 = world["s1"]
    before = await table_counts(db_session)

    ok = await client.get(URL.format(s1.id), headers={"Authorization": f"Bearer {teacher_token}"})
    denied = await client.get(URL.format(s1.id), headers={"Authorization": f"Bearer {other_school_teacher_token}"})
    broken = await client.get(URL.format(world["bad"].id), headers={"Authorization": f"Bearer {teacher_token}"})
    assert (ok.status_code, denied.status_code, broken.status_code) == (200, 403, 500)

    assert await table_counts(db_session) == before
    await db_session.refresh(s1)
    assert (s1.lu_score, s1.cu_score, s1.au_score, s1.ct_score, s1.overall_score) == (48, 74, 62, 50, 59)
