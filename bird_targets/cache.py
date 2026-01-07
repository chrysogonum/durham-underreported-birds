"""SQLite cache for eBird data.

This module provides caching functionality to store eBird API responses
locally in a SQLite database for faster repeated queries.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class BirdCache:
    """SQLite-based cache for eBird data."""

    def __init__(self, db_path: Path | str = "bird_cache.db") -> None:
        """Initialize the cache.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS regions (
                    region_code TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    parent_code TEXT
                );

                CREATE TABLE IF NOT EXISTS species (
                    species_code TEXT PRIMARY KEY,
                    common_name TEXT,
                    sci_name TEXT,
                    category_flags TEXT
                );

                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region_code TEXT,
                    species_code TEXT,
                    observation_count INTEGER,
                    obs_date TEXT,
                    UNIQUE(region_code, species_code, obs_date)
                );

                CREATE TABLE IF NOT EXISTS effort_summary (
                    region_code TEXT,
                    year INTEGER,
                    month INTEGER,
                    checklists INTEGER,
                    effort_hours REAL,
                    observers INTEGER,
                    PRIMARY KEY (region_code, year, month)
                );

                CREATE INDEX IF NOT EXISTS idx_obs_region
                    ON observations(region_code);
                CREATE INDEX IF NOT EXISTS idx_obs_species
                    ON observations(species_code);
                """
            )

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection as a context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def store_region(
        self,
        region_code: str,
        name: str,
        region_type: str = "county",
        parent_code: str | None = None,
    ) -> None:
        """Store a region in the cache."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO regions (region_code, name, type, parent_code)
                VALUES (?, ?, ?, ?)
                """,
                (region_code, name, region_type, parent_code),
            )

    def store_species(
        self,
        species_code: str,
        common_name: str,
        sci_name: str | None = None,
        category_flags: str | None = None,
    ) -> None:
        """Store a species in the cache."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO species
                    (species_code, common_name, sci_name, category_flags)
                VALUES (?, ?, ?, ?)
                """,
                (species_code, common_name, sci_name, category_flags),
            )

    def get_species(self, species_code: str) -> dict[str, Any] | None:
        """Get species data from the cache."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM species WHERE species_code = ?",
                (species_code,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    def get_all_species(self) -> list[dict[str, Any]]:
        """Get all species from the cache."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM species").fetchall()
            return [dict(row) for row in rows]
