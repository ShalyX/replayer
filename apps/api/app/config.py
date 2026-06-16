from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./replayer_dev.db"
    api_key: str = "dev-key"
    genlayer_mode: str = "mock"
    genlayer_contract_address: str = "0xB8AEf7ab07e1A05e95Ec3B0511308213b93AdE87"
    genlayer_account_password: str = ""
    genlayer_explorer_base_url: str = "https://explorer-studio.genlayer.com/tx"

    model_config = SettingsConfigDict(env_file="../../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
