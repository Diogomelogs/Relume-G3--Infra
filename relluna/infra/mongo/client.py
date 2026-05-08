from __future__ import annotations

from dataclasses import dataclass
from pymongo import MongoClient
from pymongo.database import Database

from relluna.infra.secrets import get_secret


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db_name: str

    @staticmethod
    def from_env() -> "MongoSettings":
        uri = (
            get_secret("MONGO_URI", default="")
            or get_secret("MONGODB_URI", default="")
        )
        db_name = (
            get_secret("MONGO_DB", default="")
            or get_secret("MONGODB_DB", default="")
        )
        if not uri:
            raise RuntimeError("Missing env var: MONGO_URI (or legacy MONGODB_URI)")
        if not db_name:
            raise RuntimeError("Missing env var: MONGO_DB (or legacy MONGODB_DB)")
        return MongoSettings(uri=uri, db_name=db_name)


def get_db(settings: MongoSettings | None = None) -> Database:
    s = settings or MongoSettings.from_env()
    client = MongoClient(s.uri)
    return client[s.db_name]
