import hashlib
import os
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Dict

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession

# ------------------------------------------------------------------------------
# TEST ISOLATION: this block must stay above every backend.app import.
#
# Settings and the database engine are built when their modules are imported, and
# importing storage_service creates the upload directory. Redirecting them later
# would be too late, so each run gets a throwaway folder first, and the paths are
# checked before the application is imported.
# ------------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_DB = REPO_ROOT / "lumeneios.db"
ORIGINAL_UPLOADS = REPO_ROOT / "storage_uploads"


class IsolationError(RuntimeError):
    """Raised when tests could touch real project data. Aborts the run."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_originals() -> Dict[str, str]:
    """Map each original path, relative to the repo, to its SHA-256 ("<dir>" for folders)."""
    snapshot = {
        path.relative_to(REPO_ROOT).as_posix(): _file_sha256(path)
        for path in REPO_ROOT.glob("lumeneios.db*")
        if path.is_file()
    }
    if ORIGINAL_UPLOADS.is_dir():
        snapshot[ORIGINAL_UPLOADS.relative_to(REPO_ROOT).as_posix()] = "<dir>"
        for path in ORIGINAL_UPLOADS.rglob("*"):
            relative = path.relative_to(REPO_ROOT).as_posix()
            snapshot[relative] = "<dir>" if path.is_dir() else _file_sha256(path)
    return snapshot


def _assert_strictly_inside(path, root: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise IsolationError(f"{label} is not inside the test directory {root}: {resolved}")
    return resolved


def _assert_isolated(db_url, upload_dir) -> None:
    """Fail closed unless the database file and upload folder are inside TEST_DIR."""
    try:
        url = make_url(db_url)
    except ArgumentError as exc:
        raise IsolationError("Test database URL could not be parsed.") from exc

    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise IsolationError(
            f"Tests require a SQLite database file, got backend '{url.get_backend_name()}'."
        )

    db_path = _assert_strictly_inside(url.database, TEST_DIR, "Test database")
    uploads = _assert_strictly_inside(upload_dir, TEST_DIR, "Test upload directory")
    if db_path == ORIGINAL_DB or uploads.is_relative_to(ORIGINAL_UPLOADS):
        raise IsolationError("Test paths point at original project data.")


def _assert_originals_unchanged() -> None:
    current = _snapshot_originals()
    added = sorted(set(current) - set(ORIGINAL_SNAPSHOT))
    removed = sorted(set(ORIGINAL_SNAPSHOT) - set(current))
    changed = sorted(
        path for path in set(current) & set(ORIGINAL_SNAPSHOT)
        if current[path] != ORIGINAL_SNAPSHOT[path]
    )
    if added or removed or changed:
        raise IsolationError(
            f"Original project data changed. Added: {added}; removed: {removed}; changed: {changed}."
        )


ORIGINAL_SNAPSHOT = _snapshot_originals()

# Checked before mkdtemp so a temp location inside the repo never gets written to.
if Path(tempfile.gettempdir()).resolve().is_relative_to(REPO_ROOT):
    raise IsolationError("The system temp directory is inside the repository.")

TEST_DIR = Path(tempfile.mkdtemp(prefix="lumeneios-tests-")).resolve()

# Assigned rather than defaulted, so these also override any exported value or .env file.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(TEST_DIR / 'test.db').as_posix()}"
os.environ["STORAGE_LOCAL_DIR"] = str(TEST_DIR / "uploads")
os.environ["DEMO_MODE"] = "true"  # Exercise the legacy demo paths in the isolated test app.

# Guard phase 1: config.py only reads settings, so nothing has been written or connected yet.
from backend.app.core.config import settings  # noqa: E402

_assert_isolated(settings.DATABASE_URL, settings.STORAGE_LOCAL_DIR)

from backend.app.main import app  # noqa: E402
from backend.app.core.security import create_access_token  # noqa: E402
from backend.app.db.session import engine, init_db, AsyncSessionLocal  # noqa: E402
from backend.tests.sample_seed import seed_database_if_empty  # noqa: E402
from backend.app.services.storage_service import storage_service  # noqa: E402

# Guard phase 2: check the live objects. The engine connects lazily, so it hasn't connected yet.
_assert_isolated(engine.url, storage_service.upload_dir)


def pytest_unconfigure(config):
    # Removes this run's temp folder only. A folder still held open is left in the system temp.
    shutil.rmtree(TEST_DIR, ignore_errors=True)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    _assert_isolated(engine.url, storage_service.upload_dir)
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database_if_empty(session)
    yield
    try:
        _assert_originals_unchanged()
    finally:
        try:
            await engine.dispose()
        except Exception as exc:
            # Must not hide a safety failure raised above.
            warnings.warn(f"Test engine disposal failed: {exc}")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_token() -> str:
    return create_access_token("user-admin", school_id="school-1", role="admin")


@pytest.fixture
def principal_token() -> str:
    return create_access_token("user-principal-1", school_id="school-1", role="principal")


@pytest.fixture
def teacher_token() -> str:
    return create_access_token("user-teacher-1", school_id="school-1", role="teacher")


@pytest.fixture
def student_token() -> str:
    return create_access_token("user-student-1", school_id="school-1", role="student")


@pytest.fixture
def parent_token() -> str:
    return create_access_token("user-parent-1", school_id="school-1", role="parent")


@pytest.fixture
def other_school_teacher_token() -> str:
    return create_access_token("user-teacher-3", school_id="school-3", role="teacher")

