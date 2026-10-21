from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    tour_api_key: str = ""
    kma_api_key: str = ""
    kakao_rest_api_key: str = ""
    anthropic_api_key: str = ""
    database_url: str = ""


settings = Settings()
