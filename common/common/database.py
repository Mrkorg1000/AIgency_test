from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from common.config import settings


# Database engine for async operations
engine = create_async_engine(settings.database_url)

# Session factory for creating database sessions
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to provide database sessions.
    
    Yields:
        AsyncSession: Database session that will be automatically closed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()