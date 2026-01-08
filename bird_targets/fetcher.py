"""Data fetcher for eBird observations.

Fetches and caches eBird data for Durham County and adjacent regions.
"""

from __future__ import annotations

import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from bird_targets.ebird_client import EBirdAPIError, EBirdClient

# Sampling configuration
SAMPLES_PER_YEAR = 12  # Sample once per month on average
MIN_SAMPLES_TOTAL = 24  # Minimum samples across all years

# Durham County and its adjacent regions
DURHAM_REGION = {
    "code": "US-NC-063",
    "name": "Durham County",
}

ADJACENT_REGIONS = [
    {"code": "US-NC-135", "name": "Orange County"},
    {"code": "US-NC-183", "name": "Wake County"},
    {"code": "US-NC-037", "name": "Chatham County"},
    {"code": "US-NC-077", "name": "Granville County"},
    {"code": "US-NC-145", "name": "Person County"},
]

# Default exclusion categories
DEFAULT_EXCLUSIONS = {
    "categories": ["exotic", "spuh", "slash", "hybrid", "domestic", "form"],
    "species_codes": [],  # Can add specific species codes to exclude
}


class EBirdDataCache:
    """SQLite cache for eBird data."""

    def __init__(self, cache_dir: Path) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "ebird_cache.db"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS regions (
                    region_code TEXT PRIMARY KEY,
                    name TEXT,
                    is_target INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS species_observations (
                    region_code TEXT,
                    species_code TEXT,
                    common_name TEXT,
                    sci_name TEXT,
                    observation_count INTEGER,
                    PRIMARY KEY (region_code, species_code)
                );

                CREATE TABLE IF NOT EXISTS region_stats (
                    region_code TEXT PRIMARY KEY,
                    total_checklists INTEGER,
                    total_species INTEGER,
                    fetch_date TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_species_obs_region
                    ON species_observations(region_code);
                CREATE INDEX IF NOT EXISTS idx_species_obs_species
                    ON species_observations(species_code);
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

    def set_metadata(self, key: str, value: str) -> None:
        """Store metadata."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_metadata(self, key: str) -> str | None:
        """Get metadata value."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def store_region(
        self, region_code: str, name: str, is_target: bool = False
    ) -> None:
        """Store a region."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO regions
                   (region_code, name, is_target) VALUES (?, ?, ?)""",
                (region_code, name, 1 if is_target else 0),
            )

    def store_region_stats(
        self,
        region_code: str,
        total_checklists: int,
        total_species: int,
    ) -> None:
        """Store region statistics."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO region_stats
                   (region_code, total_checklists, total_species, fetch_date)
                   VALUES (?, ?, ?, ?)""",
                (
                    region_code,
                    total_checklists,
                    total_species,
                    datetime.now().isoformat(),
                ),
            )

    def store_species_observation(
        self,
        region_code: str,
        species_code: str,
        common_name: str,
        sci_name: str,
        observation_count: int,
    ) -> None:
        """Store a species observation count for a region."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO species_observations
                   (region_code, species_code, common_name, sci_name,
                    observation_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (region_code, species_code, common_name, sci_name, observation_count),
            )

    def get_target_region(self) -> dict[str, Any] | None:
        """Get the target region data."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM regions WHERE is_target = 1").fetchone()
            if not row:
                return None

            region_code = row["region_code"]
            stats = conn.execute(
                "SELECT * FROM region_stats WHERE region_code = ?",
                (region_code,),
            ).fetchone()

            species = conn.execute(
                """SELECT species_code, common_name, observation_count
                   FROM species_observations WHERE region_code = ?""",
                (region_code,),
            ).fetchall()

            return {
                "region_code": region_code,
                "name": row["name"],
                "checklists_total": stats["total_checklists"] if stats else 0,
                "species": [
                    {
                        "species_code": s["species_code"],
                        "common_name": s["common_name"],
                        "observation_count": s["observation_count"],
                    }
                    for s in species
                ],
            }

    def get_adjacent_regions(self) -> list[dict[str, Any]]:
        """Get adjacent region data."""
        with self._get_connection() as conn:
            regions = conn.execute(
                "SELECT * FROM regions WHERE is_target = 0"
            ).fetchall()

            result = []
            for row in regions:
                region_code = row["region_code"]
                stats = conn.execute(
                    "SELECT * FROM region_stats WHERE region_code = ?",
                    (region_code,),
                ).fetchone()

                species = conn.execute(
                    """SELECT species_code, common_name, observation_count
                       FROM species_observations WHERE region_code = ?""",
                    (region_code,),
                ).fetchall()

                result.append(
                    {
                        "region_code": region_code,
                        "name": row["name"],
                        "checklists_total": stats["total_checklists"] if stats else 0,
                        "species": [
                            {
                                "species_code": s["species_code"],
                                "common_name": s["common_name"],
                                "observation_count": s["observation_count"],
                            }
                            for s in species
                        ],
                    }
                )

            return result

    def export_to_fixtures_format(self) -> tuple[dict, dict, dict]:
        """Export cached data to the same format as fixtures.

        Returns:
            Tuple of (durham_data, adjacent_data, regions_data)
        """
        target = self.get_target_region()
        adjacent = self.get_adjacent_regions()

        if not target:
            raise ValueError("No target region data in cache")

        durham_data = {
            "region_code": target["region_code"],
            "checklists_total": target["checklists_total"],
            "species": target["species"],
        }

        adjacent_data = {"regions": adjacent}

        regions_data = {
            "target_region": {
                "code": target["region_code"],
                "name": target["name"],
                "state": "NC",
            },
            "adjacent_regions": [
                {"code": r["region_code"], "name": r["name"], "state": "NC"}
                for r in adjacent
            ],
        }

        return durham_data, adjacent_data, regions_data


def generate_sample_dates(
    years: int, samples_per_year: int = SAMPLES_PER_YEAR
) -> list[datetime]:
    """Generate random sample dates across the specified time period.

    Samples are distributed across months to capture seasonal variation.

    Args:
        years: Number of years to sample
        samples_per_year: Number of samples per year

    Returns:
        List of datetime objects representing sample dates
    """
    end_date = datetime.now() - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=365 * years)

    # Ensure we have enough samples
    total_samples = max(MIN_SAMPLES_TOTAL, years * samples_per_year)

    # Generate samples distributed by month to ensure seasonal coverage
    samples = []
    days_in_period = (end_date - start_date).days

    # Sample evenly across the period with some randomization
    interval = days_in_period / total_samples
    for i in range(total_samples):
        # Add some jitter to avoid always hitting the same day of month
        base_offset = int(i * interval)
        jitter = random.randint(0, max(1, int(interval * 0.5)))
        offset = min(base_offset + jitter, days_in_period - 1)
        sample_date = start_date + timedelta(days=offset)
        samples.append(sample_date)

    return sorted(samples)


def fetch_region_data(
    client: EBirdClient,
    region_code: str,
    years: int = 5,
    verbose: bool = True,
) -> tuple[int, dict[str, dict]]:
    """Fetch observation data for a region over multiple years.

    Samples historical dates to build species frequency data.

    Args:
        client: eBird API client
        region_code: Region code to fetch
        years: Number of years of data to fetch
        verbose: Print progress messages

    Returns:
        Tuple of (total_checklists_estimate, species_data)
        where species_data maps species_code to {common_name, sci_name, count}
    """
    species_data: dict[str, dict] = {}
    total_checklists = 0
    checklists_sampled = 0

    # Try to get overall stats
    try:
        stats = client.get_region_stats(region_code)
        if "numChecklists" in stats:
            total_checklists = stats["numChecklists"]
        if verbose:
            print(f"    Stats: {total_checklists} total checklists on record")
    except EBirdAPIError as e:
        if verbose:
            print(f"    Stats endpoint unavailable: {e}")

    # Generate sample dates across the time period
    sample_dates = generate_sample_dates(years)
    if verbose:
        print(f"    Sampling {len(sample_dates)} historical dates...")

    # Fetch observations for each sample date
    successful_samples = 0
    for i, sample_date in enumerate(sample_dates):
        try:
            observations = client.get_historic_observations(
                region_code,
                sample_date.year,
                sample_date.month,
                sample_date.day,
            )

            # Count unique checklists in this sample
            checklist_ids = set()
            for obs in observations:
                code = obs.get("speciesCode")
                if not code:
                    continue

                # Track checklists
                sub_id = obs.get("subId")
                if sub_id:
                    checklist_ids.add(sub_id)

                # Aggregate species counts
                if code not in species_data:
                    species_data[code] = {
                        "common_name": obs.get("comName", "Unknown"),
                        "sci_name": obs.get("sciName", ""),
                        "count": 0,
                    }
                species_data[code]["count"] += 1

            checklists_sampled += len(checklist_ids)
            successful_samples += 1

            # Progress indicator every 10 samples
            if verbose and (i + 1) % 10 == 0:
                print(f"      ... {i + 1}/{len(sample_dates)} dates sampled")

        except EBirdAPIError as e:
            # Some dates may have no data, that's ok
            if verbose and "404" not in str(e):
                print(f"      Date {sample_date.date()}: {e}")

    if verbose:
        print(
            f"    Found {len(species_data)} species across "
            f"{successful_samples} dates ({checklists_sampled} checklists)"
        )

    # If we couldn't get stats, estimate from samples
    if total_checklists == 0 and checklists_sampled > 0:
        # Rough extrapolation: if we sampled N dates and found M checklists,
        # estimate total = M * (365 * years / N)
        days_sampled = successful_samples
        days_total = 365 * years
        total_checklists = int(checklists_sampled * days_total / max(days_sampled, 1))
        if verbose:
            print(f"    Estimated ~{total_checklists} total checklists")

    return total_checklists, species_data


def fetch_all_regions(
    cache_dir: Path,
    years: int = 5,
    verbose: bool = True,
) -> EBirdDataCache:
    """Fetch data for Durham and all adjacent regions.

    Args:
        cache_dir: Directory to store cache
        years: Number of years of historical data
        verbose: Print progress messages

    Returns:
        EBirdDataCache instance with fetched data
    """
    from bird_targets.ebird_client import require_api_key

    api_key = require_api_key()
    client = EBirdClient(api_key)
    cache = EBirdDataCache(cache_dir)

    # Store metadata
    cache.set_metadata("fetch_date", datetime.now().isoformat())
    cache.set_metadata("years", str(years))

    # Fetch Durham (target region)
    if verbose:
        print(f"Fetching {DURHAM_REGION['name']}...")
    cache.store_region(DURHAM_REGION["code"], DURHAM_REGION["name"], is_target=True)

    total_cl, species = fetch_region_data(client, DURHAM_REGION["code"], years, verbose)
    cache.store_region_stats(DURHAM_REGION["code"], total_cl, len(species))

    for code, data in species.items():
        cache.store_species_observation(
            DURHAM_REGION["code"],
            code,
            data["common_name"],
            data["sci_name"],
            data["count"],
        )

    # Fetch adjacent regions
    for region in ADJACENT_REGIONS:
        if verbose:
            print(f"Fetching {region['name']}...")
        cache.store_region(region["code"], region["name"], is_target=False)

        total_cl, species = fetch_region_data(client, region["code"], years, verbose)
        cache.store_region_stats(region["code"], total_cl, len(species))

        for code, data in species.items():
            cache.store_species_observation(
                region["code"],
                code,
                data["common_name"],
                data["sci_name"],
                data["count"],
            )

    if verbose:
        print(f"Data cached to {cache_dir}")

    return cache
