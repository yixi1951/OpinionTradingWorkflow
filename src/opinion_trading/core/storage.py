"""Pluggable storage backends: file (default) / MySQL / MongoDB / Redis.

Env:
  STORAGE_BACKEND=file|mysql|mongo|redis|multi
  MYSQL_URL=mysql+pymysql://user:pass@127.0.0.1:3306/opinion
  MONGO_URL=mongodb://127.0.0.1:27017
  MONGO_DB=opinion_trading
  REDIS_URL=redis://127.0.0.1:6379/0

When optional drivers are missing or URLs unset, operations fall back to files
so local/CI runs stay zero-dependency.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class StorageBackend(ABC):
    @abstractmethod
    def save_structured(self, table: str, rows: Iterable[Dict[str, Any]]) -> int: ...

    @abstractmethod
    def save_documents(self, collection: str, docs: Iterable[Dict[str, Any]]) -> int: ...

    @abstractmethod
    def cache_get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None: ...


class FileStorage(StorageBackend):
    def __init__(self, root: str = "data/db_fallback") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}

    def save_structured(self, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        path = self.root / f"{table}.jsonl"
        n = 0
        with path.open("a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                n += 1
        return n

    def save_documents(self, collection: str, docs: Iterable[Dict[str, Any]]) -> int:
        return self.save_structured(f"docs_{collection}", docs)

    def cache_get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._cache[key] = value


class MySQLStorage(StorageBackend):
    """Structured store for symbols / scores / signals."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._engine = None

    def _connect(self):
        if self._engine is not None:
            return self._engine
        try:
            from sqlalchemy import create_engine  # type: ignore

            self._engine = create_engine(self.url, pool_pre_ping=True)
            return self._engine
        except Exception:
            return None

    def save_structured(self, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        engine = self._connect()
        rows_list = list(rows)
        if engine is None or not rows_list:
            return FileStorage().save_structured(table, rows_list)
        try:
            import pandas as pd

            df = pd.DataFrame(rows_list)
            df.to_sql(table, engine, if_exists="append", index=False, method="multi")
            return len(rows_list)
        except Exception:
            return FileStorage().save_structured(table, rows_list)

    def save_documents(self, collection: str, docs: Iterable[Dict[str, Any]]) -> int:
        # MySQL path stores docs as JSON column table
        return self.save_structured(f"docs_{collection}", docs)

    def cache_get(self, key: str) -> Optional[Any]:
        return None

    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        return None


class MongoStorage(StorageBackend):
    def __init__(self, url: str, db_name: str = "opinion_trading") -> None:
        self.url = url
        self.db_name = db_name
        self._client = None

    def _db(self):
        if self._client is not None:
            return self._client[self.db_name]
        try:
            from pymongo import MongoClient  # type: ignore

            self._client = MongoClient(self.url, serverSelectionTimeoutMS=2000)
            self._client.admin.command("ping")
            return self._client[self.db_name]
        except Exception:
            self._client = None
            return None

    def save_structured(self, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        return self.save_documents(table, rows)

    def save_documents(self, collection: str, docs: Iterable[Dict[str, Any]]) -> int:
        db = self._db()
        docs_list = list(docs)
        if db is None or not docs_list:
            return FileStorage().save_documents(collection, docs_list)
        try:
            db[collection].insert_many(docs_list, ordered=False)
            return len(docs_list)
        except Exception:
            return FileStorage().save_documents(collection, docs_list)

    def cache_get(self, key: str) -> Optional[Any]:
        return None

    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        return None


class RedisStorage(StorageBackend):
    def __init__(self, url: str) -> None:
        self.url = url
        self._r = None
        self._file = FileStorage()

    def _client(self):
        if self._r is not None:
            return self._r
        try:
            import redis  # type: ignore

            self._r = redis.Redis.from_url(self.url, decode_responses=True)
            self._r.ping()
            return self._r
        except Exception:
            self._r = None
            return None

    def save_structured(self, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        return self._file.save_structured(table, rows)

    def save_documents(self, collection: str, docs: Iterable[Dict[str, Any]]) -> int:
        return self._file.save_documents(collection, docs)

    def cache_get(self, key: str) -> Optional[Any]:
        client = self._client()
        if client is None:
            return self._file.cache_get(key)
        raw = client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        client = self._client()
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if client is None:
            self._file.cache_set(key, value, ttl_seconds)
            return
        client.setex(key, ttl_seconds, payload)


class MultiStorage(StorageBackend):
    """Fan-out: structured→MySQL, documents→Mongo, cache→Redis, always file backup."""

    def __init__(
        self,
        mysql: Optional[StorageBackend] = None,
        mongo: Optional[StorageBackend] = None,
        redis: Optional[StorageBackend] = None,
        file: Optional[FileStorage] = None,
    ) -> None:
        self.mysql = mysql
        self.mongo = mongo
        self.redis = redis
        self.file = file or FileStorage()

    def save_structured(self, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        rows_list = list(rows)
        n = 0
        if self.mysql:
            n = max(n, self.mysql.save_structured(table, rows_list))
        n = max(n, self.file.save_structured(table, rows_list))
        return n

    def save_documents(self, collection: str, docs: Iterable[Dict[str, Any]]) -> int:
        docs_list = list(docs)
        n = 0
        if self.mongo:
            n = max(n, self.mongo.save_documents(collection, docs_list))
        n = max(n, self.file.save_documents(collection, docs_list))
        return n

    def cache_get(self, key: str) -> Optional[Any]:
        if self.redis:
            val = self.redis.cache_get(key)
            if val is not None:
                return val
        return self.file.cache_get(key)

    def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        if self.redis:
            self.redis.cache_set(key, value, ttl_seconds)
        self.file.cache_set(key, value, ttl_seconds)


def get_storage() -> StorageBackend:
    backend = os.environ.get("STORAGE_BACKEND", "file").strip().lower()
    mysql_url = os.environ.get("MYSQL_URL", "").strip()
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    redis_url = os.environ.get("REDIS_URL", "").strip()
    mongo_db = os.environ.get("MONGO_DB", "opinion_trading")

    if backend == "mysql" and mysql_url:
        return MySQLStorage(mysql_url)
    if backend == "mongo" and mongo_url:
        return MongoStorage(mongo_url, mongo_db)
    if backend == "redis" and redis_url:
        return RedisStorage(redis_url)
    if backend == "multi":
        return MultiStorage(
            mysql=MySQLStorage(mysql_url) if mysql_url else None,
            mongo=MongoStorage(mongo_url, mongo_db) if mongo_url else None,
            redis=RedisStorage(redis_url) if redis_url else None,
        )
    return FileStorage()
