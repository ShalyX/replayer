from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./replayer_dev.db"
    api_key: str = "dev-key"
    admin_api_key: str = ""
    genlayer_mode: str = "live"
    allow_test_mocks: bool = False
    genlayer_rpc_url: str = ""
    genlayer_contract_address: str = "0xBf42bB13fb77695d42B08eCdf589Ba54eB1C361A"
    genlayer_account_password: str = ""
    genlayer_private_key: str = ""
    genlayer_network: str = "studionet"
    genlayer_explorer_base_url: str = "https://explorer-studio.genlayer.com/tx"
    genlayer_command_timeout_seconds: int = 240
    genlayer_read_attempts: int = 6
    genlayer_read_interval_seconds: int = 5
    genlayer_indexer_poll_interval: int = 15
    genlayer_read_timeout: int = 30
    genlayer_confirmation_depth: int = 0
    genlayer_start_block: int = 0
    genlayer_proof_event_id: str = ""
    genlayer_proof_transaction_hash: str = ""
    genlayer_proof_transactions_json: str = "{}"

    model_config = SettingsConfigDict(env_file="../../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
