"""Local parquet cache with incremental-update friendly semantics."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


class ParquetCache:
    """Small wrapper around parquet files used by data providers and pipelines."""

    def __init__(self, root: str | Path = "data/cached") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, namespace: str, key: str) -> Path:
        safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        directory = self.root / namespace
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{safe_key}.parquet"

    def exists(self, namespace: str, key: str) -> bool:
        return self.path_for(namespace, key).exists()

    def read(self, namespace: str, key: str) -> pd.DataFrame:
        path = self.path_for(namespace, key)
        LOGGER.info("Reading cache: %s", path)
        return pd.read_parquet(path)

    def write(self, frame: pd.DataFrame, namespace: str, key: str) -> Path:
        path = self.path_for(namespace, key)
        LOGGER.info("Writing cache: %s rows=%s", path, len(frame))
        frame.to_parquet(path)
        return path

    def update_time_series(
        self,
        existing: pd.DataFrame | None,
        incoming: pd.DataFrame,
        subset: list[str] | None = None,
    ) -> pd.DataFrame:
        """Append new rows and de-duplicate by index or optional subset columns."""

        if existing is None or existing.empty:
            return incoming.sort_index()
        combined = pd.concat([existing, incoming]).sort_index()
        if subset:
            index_names = list(combined.index.names)
            combined = combined.reset_index().drop_duplicates(subset=subset, keep="last").set_index(index_names)
        else:
            combined = combined[~combined.index.duplicated(keep="last")]
        return combined.sort_index()
