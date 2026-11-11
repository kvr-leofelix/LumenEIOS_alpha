"""The app's roster seed: IIT Mandi -> JNV Bengaluru / Dakshana Kottayam, run on its own database."""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.security import verify_password
from backend.app.db.session import Base
from backend.app.models.entities import ClassSection, ParentStudentLink, School, SchoolMembership, Student, User
from backend.app.modules.differentiated_homework.models import StudentAccountLink
from backend.app.seed.seed_data import ROOT_PERSONA_EMAILS, seed_database_if_empty


@pytest_asyncio.fixture
async def roster(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'roster.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await seed_database_if_empty(session)
        await seed_database_if_empty(session)  # second run must be a no-op
        yield session
    await engine.dispose()


async def all_rows(session, model):
    return (await session.execute(select(model))).scalars().all()


@pytest.mark.asyncio
async def test_roster_has_only_the_new_hierarchy(roster):
    schools = {s.id: s.name for s in await all_rows(roster, School)}
    assert schools == {"school-1": "JNV Bengaluru", "school-2": "Dakshana Kottayam"}

    users = {u.email: u for u in await all_rows(roster, User)}
    by_role = {}
    for user in users.values():
        by_role.setdefault(user.role, set()).add(user.name)
    assert by_role == {
        "admin": {"IIT Mandi"},
        "principal": {"JNV Bengaluru", "Dakshana Kottayam"},
        "teacher": {"Arvind", "Garima", "Kamlesh", "Preeti"},
        "student": {"Gurleen", "Agam", "Pranay", "Tanv", "Grishma", "KVR"},
        "parent": {f"{n} ki Mummy" for n in ["Gurleen", "Agam", "Pranay", "Tanv", "Grishma", "KVR"]},
    }
    assert all(verify_password("demo123", u.hashed_password) for u in users.values())
    assert set(ROOT_PERSONA_EMAILS.values()) <= set(users)


@pytest.mark.asyncio
async def test_schools_teachers_and_students_follow_the_hierarchy(roster):
    users = {u.name: u for u in await all_rows(roster, User)}
    jnv, dakshana = "school-1", "school-2"
    for name in ["Arvind", "Garima", "Gurleen", "Agam", "Pranay", "JNV Bengaluru"]:
        assert users[name].school_id == jnv, name
    for name in ["Kamlesh", "Preeti", "Tanv", "Grishma", "KVR", "Dakshana Kottayam"]:
        assert users[name].school_id == dakshana, name

    admin_schools = {m.school_id for m in await all_rows(roster, SchoolMembership) if m.user_id == users["IIT Mandi"].id}
    assert admin_schools == {jnv, dakshana}

    students = {s.name: s for s in await all_rows(roster, Student)}
    grades = {name: int(s.class_name.split()[1].split("-")[0]) for name, s in students.items()}
    assert grades == {"Gurleen": 6, "Agam": 7, "Pranay": 8, "Tanv": 9, "KVR": 10, "Grishma": 11}

    classes = {c.id: c for c in await all_rows(roster, ClassSection)}
    assert classes["class-jnv-6"].subject_ids_json == ["sub-sci"]
    assert classes["class-jnv-12"].subject_ids_json == ["sub-chem"]
    assert classes["class-dakshana-9"].subject_ids_json == ["sub-math", "sub-eng"]
    assert classes["class-dakshana-11"].subject_ids_json == ["sub-eng"]
    for student in students.values():
        assert classes[student.class_id].school_id == student.school_id


@pytest.mark.asyncio
async def test_each_student_has_a_login_and_one_parent(roster):
    students = await all_rows(roster, Student)
    parents = {u.id: u for u in await all_rows(roster, User) if u.role == "parent"}
    links = {link.student_id: link.parent_user_id for link in await all_rows(roster, ParentStudentLink)}
    accounts = {link.student_id: link.user_id for link in await all_rows(roster, StudentAccountLink)}

    assert len(parents) == len(students) == 6
    for student in students:
        parent = parents[links[student.id]]
        assert parent.name == f"{student.name} ki Mummy"
        assert parent.school_id == student.school_id
        assert student.parent_id == parent.id
        assert accounts[student.id] == student.id
