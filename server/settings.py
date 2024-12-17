import enum
from pathlib import Path
from tempfile import gettempdir

import dotenv
import os
from pydantic_settings import BaseSettings, SettingsConfigDict



dotenv.load_dotenv()  # Load environment variables from .env file
TEMP_DIR = Path(gettempdir())


class LogLevel(str, enum.Enum):  # noqa: WPS600
    """Possible log levels."""

    NOTSET = "NOTSET"
    INFO = "INFO"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1

    # Enable uvicorn reloading
    reload: bool = False
    # google_application_credentials: str
    openai_api_key: str
    mongodb_url: str = "mongodb://localhost:27017/"
    milvus_db_username: str = "root"
    milvus_db_password: str = ""
    milvus_db_host: str = "localhost"
    milvus_db_port: int = 19530
    milvus_db_name: str = "default"
    milvus_db_collection: str = "project_collection"

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO

    model_config = SettingsConfigDict(
        env_file=".env",  # Specify the .env file
        env_prefix="SERVER_",  # Use prefix SERVER_ for env vars
        env_file_encoding="utf-8",
    )


settings = Settings()
