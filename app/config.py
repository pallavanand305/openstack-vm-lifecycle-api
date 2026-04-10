from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenStack auth
    os_auth_url: str = "http://localhost:5000/v3"
    os_username: str = "admin"
    os_password: str = "secret"
    os_project_name: str = "admin"
    os_user_domain_name: str = "Default"
    os_project_domain_name: str = "Default"
    os_region_name: str = "RegionOne"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # Pagination defaults
    default_page_size: int = 20
    max_page_size: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
