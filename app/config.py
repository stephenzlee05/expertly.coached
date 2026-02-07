from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "expertly"
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    VAPI_SERVER_SECRET: str = ""
    ADMIN_API_KEY: str = ""
    SUMMARY_CAP: int = 5  # Max summary records per topic before consolidation

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
