from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    bot_token: str = ""
    webhook_url: Optional[str] = None
    fx_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./flyrates.db"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
