import asyncio
import pytest
import httpx
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from redis.asyncio import Redis
import time

# Test environment settings
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_password@localhost:5433/lead_triage_test"
TEST_REDIS_URL = "redis://localhost:6380/0"
TEST_INTAKE_API_URL = "http://localhost:8100"
TEST_INSIGHTS_API_URL = "http://localhost:8101"
TEST_REDIS_STREAM = "lead_events_test"
TEST_REDIS_CONSUMER_GROUP = "triage_group_test"

# Timeouts
SERVICE_READY_TIMEOUT = 60
WORKER_PROCESSING_TIMEOUT = 10


@pytest.fixture(scope="function", autouse=True)
async def wait_for_services():
    """
    Waits for all services to be ready.
    Automatically runs before all tests.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        services = {
            "intake-api": f"{TEST_INTAKE_API_URL}/leads",
            "insights-api": f"{TEST_INSIGHTS_API_URL}/leads",
        }

        for service_name, url in services.items():
            start_time = time.time()
            while time.time() - start_time < SERVICE_READY_TIMEOUT:
                try:
                    response = await client.get(url)
                    print(f"✓ {service_name} ready (status: {response.status_code})")
                    break
                except (httpx.ConnectError, httpx.RemoteProtocolError):
                    await asyncio.sleep(1)
            else:
                raise TimeoutError(f"{service_name} did not become available within {SERVICE_READY_TIMEOUT}s")

    print("✓ All services ready")


@pytest.fixture(scope="function")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client for API requests"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a database session for direct access in tests.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Redis client for direct queue access"""
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    await client.close()


@pytest.fixture(scope="function")
async def clean_database(db_session: AsyncSession):
    """Cleans database tables before each test"""
    await db_session.execute(text("DELETE FROM insights"))
    await db_session.execute(text("DELETE FROM leads"))
    await db_session.commit()
    print("✓ Database cleaned")


@pytest.fixture(scope="function")
async def clean_redis(redis_client: Redis):
    """Cleans Redis stream before each test"""
    try:
        # Instead of deleting the stream, trim all messages
        # This preserves the consumer group but removes data
        await redis_client.xtrim(TEST_REDIS_STREAM, maxlen=0, approximate=False)
        print("✓ Redis stream trimmed")
    except Exception as e:
        # If stream doesn't exist - that's okay
        print(f"✓ Redis stream trim skipped: {e}")
    
    # Clean idempotency keys
    keys = await redis_client.keys("idempotency:*")
    if keys:
        await redis_client.delete(*keys)
    
    print("✓ Redis cleaned")


@pytest.fixture(scope="function")
async def clean_env(clean_database, clean_redis):
    """Combined fixture for complete environment cleanup"""
    pass


async def wait_for_insight(
    http_client: httpx.AsyncClient,
    lead_id: str,
    timeout: int = WORKER_PROCESSING_TIMEOUT
) -> dict:
    """Waits for the worker to process the lead and create an insight"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = await http_client.get(f"{TEST_INSIGHTS_API_URL}/leads/{lead_id}/insight")
        if response.status_code == 200:
            return response.json()
        await asyncio.sleep(0.5)
    
    raise TimeoutError(f"Insight for lead {lead_id} was not created in {timeout}s")


__all__ = [
    "http_client",
    "db_session",
    "redis_client",
    "clean_database",
    "clean_redis",
    "clean_env",
    "wait_for_services",
    "wait_for_insight",
    "TEST_INTAKE_API_URL",
    "TEST_INSIGHTS_API_URL",
    "TEST_REDIS_STREAM",
]