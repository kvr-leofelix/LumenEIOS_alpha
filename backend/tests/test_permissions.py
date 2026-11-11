import pytest
from fastapi import HTTPException
from backend.app.core.permissions import (
    RoleEnum,
    has_role_permission,
    enforce_permission,
    enforce_school_access,
    PERM_MANAGE_SCHOOLS,
    PERM_CREATE_ASSESSMENT,
    PERM_SUBMIT_HOMEWORK,
)


def test_permission_matrix():
    # Admin has manage schools
    assert has_role_permission("admin", PERM_MANAGE_SCHOOLS) is True
    # Teacher does not have manage schools
    assert has_role_permission("teacher", PERM_MANAGE_SCHOOLS) is False
    # Teacher can create assessment
    assert has_role_permission("teacher", PERM_CREATE_ASSESSMENT) is True
    # Student can submit homework but cannot create assessment
    assert has_role_permission("student", PERM_SUBMIT_HOMEWORK) is True
    assert has_role_permission("student", PERM_CREATE_ASSESSMENT) is False


def test_enforce_permission_raises_forbidden():
    with pytest.raises(HTTPException) as excinfo:
        enforce_permission("student", PERM_MANAGE_SCHOOLS)
    assert excinfo.value.status_code == 403


class DummyUser:
    def __init__(self, role, school_id, memberships=None):
        self.role = role
        self.school_id = school_id
        self.memberships = memberships or []


def test_enforce_school_access_admin_bypass():
    admin = DummyUser("admin", "school-1")
    # Admin can access any target school
    assert enforce_school_access(admin, "school-5") is True


def test_enforce_school_access_cross_tenant_rejection():
    teacher_s1 = DummyUser("teacher", "school-1")
    # Teacher 1 should be able to access school-1
    assert enforce_school_access(teacher_s1, "school-1") is True
    # Teacher 1 should NOT be able to access school-3
    with pytest.raises(HTTPException) as excinfo:
        enforce_school_access(teacher_s1, "school-3")
    assert excinfo.value.status_code == 403
    assert "Cross-school tenant access denied" in excinfo.value.detail


@pytest.mark.asyncio
async def test_api_role_route_enforcement(client, student_token, teacher_token):
    # Student attempting to access teacher-only endpoint (e.g. record disruption)
    headers = {"Authorization": f"Bearer {student_token}"}
    payload = {
        "date": "2026-11-01",
        "reason": "Unauthorized Disruption",
        "days_lost": 1.0,
        "notes": "Student trying to add disruption"
    }
    response = await client.post("/api/v1/schools/school-1/disruptions", headers=headers, json=payload)
    assert response.status_code == 403

    # Teacher should succeed
    t_headers = {"Authorization": f"Bearer {teacher_token}"}
    t_response = await client.post("/api/v1/schools/school-1/disruptions", headers=t_headers, json=payload)
    assert t_response.status_code == 201
