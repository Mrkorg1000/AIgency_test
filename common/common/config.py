from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    
    REDIS_URL: str
    REDIS_STREAM: str
    REDIS_CONSUMER_GROUP: str  
    MAX_CONCURRENT_REQUESTS: int

    BATCH_SIZE: int = 1
    STREAM_BLOCK_TIME: int
    
    LLM_ADAPTER: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @property
    def database_url(self) -> str:
        """Constructs PostgreSQL connection URL for asyncpg."""
        user = self.POSTGRES_USER
        password = self.POSTGRES_PASSWORD
        host = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


settings = Settings()