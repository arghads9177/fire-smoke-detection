"""Settings loaded from .env via pydantic-settings (see .env.example)."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # MongoDB: comma-separated host:port pairs (replica set members or a single host)
    mongo_hosts: str = "localhost:27017"
    mongo_replica_set: str = ""
    mongo_db: str = "videoAnalyticDB"
    mongo_user: str = ""
    mongo_password: str = ""
    # Defaults to the application database when empty
    mongo_auth_source: str = ""

    # API key the AI service must send on /detections and /heartbeat (X-API-Key)
    api_key: str = "changeme"

    # Dashboard origin for CORS
    cors_origin: str = "http://localhost:4200"

    # Directory of annotated snapshots, served statically at /snapshots/*
    snapshots_dir: str = "snapshots"

    @property
    def mongo_uri(self) -> str:
        credentials = ""
        if self.mongo_user:
            # quote_plus so reserved characters in the password (e.g. '#') survive the URI
            credentials = f"{quote_plus(self.mongo_user)}:{quote_plus(self.mongo_password)}@"
        uri = f"mongodb://{credentials}{self.mongo_hosts}/{self.mongo_db}"
        params = []
        if self.mongo_replica_set:
            params.append(f"replicaSet={self.mongo_replica_set}")
        if self.mongo_user:
            params.append(f"authSource={self.mongo_auth_source or self.mongo_db}")
        if params:
            uri += "?" + "&".join(params)
        return uri


@lru_cache
def get_settings() -> Settings:
    return Settings()
