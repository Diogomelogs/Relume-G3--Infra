from __future__ import annotations

import os
from dataclasses import dataclass
from pymongo import MongoClient
from pymongo.database import Database


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db_name: str

    @staticmethod
    def from_env() -> "MongoSettings":
        uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
        db_name = os.getenv("MONGO_DB") or os.getenv("MONGODB_DB")
        if not uri:
            raise RuntimeError("Missing env var: MONGO_URI (or legacy MONGODB_URI)")
        if not db_name:
            raise RuntimeError("Missing env var: MONGO_DB (or legacy MONGODB_DB)")
        return MongoSettings(uri=uri, db_name=db_name)


def get_db(settings: MongoSettings | None = None) -> Database:
    s = settings or MongoSettings.from_env()
    client = MongoClient(s.uri)
    return client[s.db_name]
