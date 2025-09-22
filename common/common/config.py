from dataclasses import Field
from typing import Annotated
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
import os


class Settings(BaseSettings):
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    
    REDIS_URL: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @property
    def database_url(self) -> str:
        user = self.POSTGRES_USER
        password = self.POSTGRES_PASSWORD
        host = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


settings = Settings()