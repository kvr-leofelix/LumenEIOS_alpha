from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

Base = declarative_base()

# Engine creation
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safely migrate optional columns on documents table if upgrading existing SQLite DB
        for col_sql in [
            "ALTER TABLE documents ADD COLUMN subject_id VARCHAR(64)",
            "ALTER TABLE documents ADD COLUMN doc_type VARCHAR(50) DEFAULT 'source_material'",
            "ALTER TABLE documents ADD COLUMN content_hash VARCHAR(128)",
            "ALTER TABLE documents ADD COLUMN extracted_text TEXT",
        ]:
            try:
                await conn.execute(text(col_sql))
            except Exception:
                pass


