from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    data_go_kr_key: str = ""
    visitjeju_api_key: str = ""
    anthropic_api_key: str = ""
    database_url: str = ""

    # Spring 백엔드 주소와 서버 간 호출용 키
    backend_url: str = "http://localhost:8080"
    internal_api_key: str = ""


settings = Settings()
