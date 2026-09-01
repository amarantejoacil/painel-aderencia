from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://aderencia:aderencia@127.0.0.1:5432/aderencia"
    cors_origins: str = "http://127.0.0.1:43123,http://localhost:43123"
    azure_devops_url: str = ""
    azure_devops_organization: str = ""
    azure_devops_project: str = ""
    azure_devops_pat: str = ""
    azure_devops_field_work_date: str = ""
    azure_devops_field_activity: str = ""
    secret_encryption_key: str = ""


settings = Settings()


def azure_devops_configured_from_env() -> bool:
    return bool(
        settings.azure_devops_url.strip()
        and settings.azure_devops_organization.strip()
        and settings.azure_devops_project.strip()
        and settings.azure_devops_pat.strip()
    )


def azure_devops_configured() -> bool:
    """Compatibilidade: verifica somente variáveis de ambiente."""
    return azure_devops_configured_from_env()
