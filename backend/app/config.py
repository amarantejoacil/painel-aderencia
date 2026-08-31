from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://aderencia:aderencia@127.0.0.1:5432/aderencia"
    cors_origins: str = "http://127.0.0.1:43123,http://localhost:43123"


settings = Settings()
