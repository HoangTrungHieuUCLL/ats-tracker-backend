from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"
    jwt_secret: str
    cors_origins: str = "http://localhost:5173"

    fetch_min_seconds_per_domain: float = 3.0
    llm_min_seconds_between_calls: float = 6.0

    log_level: str = "INFO"

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
