"""Non-admins only read their own school's classes, students and analytics; admins read all."""
import pytest

OTHER_SCHOOL_CLASS = "class-pragati-8"  # school-3 in the test dataset
OWN_CLASS = "class-8a"  # school-1


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    f"/api/v1/classes/{OTHER_SCHOOL_CLASS}",
    f"/api/v1/classes/{OTHER_SCHOOL_CLASS}/students",
    f"/api/v1/classes/{OTHER_SCHOOL_CLASS}/competency-analytics",
    "/api/v1/schools/school-3",
    "/api/v1/schools/school-3/classes",
    "/api/v1/schools/school-3/competency-analytics",
    "/api/v1/students/student-18/competencies",
])
async def test_teacher_cannot_read_another_school(client, teacher_token, admin_token, path):
    assert (await client.get(path, headers=auth(teacher_token))).status_code == 403
    assert (await client.get(path, headers=auth(admin_token))).status_code == 200


@pytest.mark.asyncio
async def test_principal_cannot_add_classes_or_teachers_to_another_school(client, principal_token):
    headers = auth(principal_token)  # principal of school-1
    teacher = await client.post("/api/v1/teachers", headers=headers, json={
        "name": "Cross School", "email": "cross.school@lumeneios.demo", "school_id": "school-3", "designation": "Teacher"})
    assert teacher.status_code == 403
    section = await client.post("/api/v1/classes", headers=headers, json={"name": "10Z", "school_id": "school-3"})
    assert section.status_code == 403


@pytest.mark.asyncio
async def test_teacher_reads_own_school_and_lists_only_it(client, teacher_token, admin_token):
    students = await client.get(f"/api/v1/classes/{OWN_CLASS}/students", headers=auth(teacher_token))
    assert students.status_code == 200 and students.json()

    teacher_schools = {s["id"] for s in (await client.get("/api/v1/schools", headers=auth(teacher_token))).json()}
    admin_schools = {s["id"] for s in (await client.get("/api/v1/schools", headers=auth(admin_token))).json()}
    assert "school-1" in teacher_schools and "school-3" not in teacher_schools
    assert {"school-1", "school-3"} <= admin_schools

    comparison = (await client.get("/api/v1/analytics/school-comparison", headers=auth(teacher_token))).json()
    assert [item["name"] for item in comparison] == ["Sunrise Public School"]
