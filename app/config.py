from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./perspectives.db"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    sp_email: str = ""
    sp_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
