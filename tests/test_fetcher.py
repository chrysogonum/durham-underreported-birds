"""Tests for the fetcher module."""

import tempfile
from pathlib import Path
from unittest import mock

from bird_targets.fetcher import (
    ADJACENT_REGIONS,
    DURHAM_REGION,
    EBirdDataCache,
    fetch_region_data,
)


class TestEBirdDataCache:
    """Tests for EBirdDataCache class."""

    def test_init_creates_directory(self) -> None:
        """Should create cache directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "new_cache"
            assert not cache_dir.exists()

            _cache = EBirdDataCache(cache_dir)  # noqa: F841

            assert cache_dir.exists()
            assert (cache_dir / "ebird_cache.db").exists()

    def test_store_and_get_metadata(self) -> None:
        """Should store and retrieve metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EBirdDataCache(Path(tmpdir))

            cache.set_metadata("test_key", "test_value")
            result = cache.get_metadata("test_key")

            assert result == "test_value"

    def test_get_missing_metadata_returns_none(self) -> None:
        """Should return None for missing metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EBirdDataCache(Path(tmpdir))

            result = cache.get_metadata("nonexistent")

            assert result is None

    def test_store_region(self) -> None:
        """Should store region data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EBirdDataCache(Path(tmpdir))

            cache.store_region("US-NC-063", "Durham County", is_target=True)
            cache.store_region_stats("US-NC-063", 5000, 250)

            target = cache.get_target_region()

            assert target is not None
            assert target["region_code"] == "US-NC-063"
            assert target["name"] == "Durham County"
            assert target["checklists_total"] == 5000

    def test_store_species_observation(self) -> None:
        """Should store species observation counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EBirdDataCache(Path(tmpdir))

            cache.store_region("US-NC-063", "Durham County", is_target=True)
            cache.store_region_stats("US-NC-063", 1000, 10)
            cache.store_species_observation(
                "US-NC-063", "carwre", "Carolina Wren", "Thryothorus ludovicianus", 800
            )
            cache.store_species_observation(
                "US-NC-063", "norcar", "Northern Cardinal", "Cardinalis cardinalis", 900
            )

            target = cache.get_target_region()

            assert len(target["species"]) == 2
            species_codes = {s["species_code"] for s in target["species"]}
            assert "carwre" in species_codes
            assert "norcar" in species_codes

    def test_get_adjacent_regions(self) -> None:
        """Should return adjacent regions (not target)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EBirdDataCache(Path(tmpdir))

            # Add target region
            cache.store_region("US-NC-063", "Durham County", is_target=True)
            cache.store_region_stats("US-NC-063", 5000, 250)

            # Add adjacent regions
            cache.store_region("US-NC-135", "Orange County", is_target=False)
            cache.store_region_stats("US-NC-135", 4000, 200)
            cache.store_region("US-NC-183", "Wake County", is_target=False)
            cache.store_region_stats("US-NC-183", 12000, 300)

            adjacent = cache.get_adjacent_regions()

            assert len(adjacent) == 2
            region_codes = {r["region_code"] for r in adjacent}
            assert "US-NC-135" in region_codes
            assert "US-NC-183" in region_codes
            assert "US-NC-063" not in region_codes  # Target should not be included

    def test_export_to_fixtures_format(self) -> None:
        """Should export data in same format as fixtures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EBirdDataCache(Path(tmpdir))

            # Set up target region
            cache.store_region("US-NC-063", "Durham County", is_target=True)
            cache.store_region_stats("US-NC-063", 5000, 2)
            cache.store_species_observation(
                "US-NC-063", "carwre", "Carolina Wren", "", 4500
            )

            # Set up adjacent region
            cache.store_region("US-NC-135", "Orange County", is_target=False)
            cache.store_region_stats("US-NC-135", 4000, 1)
            cache.store_species_observation(
                "US-NC-135", "carwre", "Carolina Wren", "", 3600
            )

            durham, adjacent, regions = cache.export_to_fixtures_format()

            # Check durham_data format
            assert durham["region_code"] == "US-NC-063"
            assert durham["checklists_total"] == 5000
            assert len(durham["species"]) == 1

            # Check adjacent_data format
            assert "regions" in adjacent
            assert len(adjacent["regions"]) == 1


class TestRegionConstants:
    """Tests for region constants."""

    def test_durham_region_code(self) -> None:
        """Should have correct Durham County code."""
        assert DURHAM_REGION["code"] == "US-NC-063"
        assert DURHAM_REGION["name"] == "Durham County"

    def test_adjacent_regions_count(self) -> None:
        """Should have 5 adjacent regions."""
        assert len(ADJACENT_REGIONS) == 5

    def test_adjacent_regions_codes(self) -> None:
        """Should have correct adjacent region codes."""
        codes = {r["code"] for r in ADJACENT_REGIONS}
        assert "US-NC-135" in codes  # Orange
        assert "US-NC-183" in codes  # Wake
        assert "US-NC-037" in codes  # Chatham
        assert "US-NC-077" in codes  # Granville
        assert "US-NC-145" in codes  # Person


class TestFetchRegionData:
    """Tests for fetch_region_data function."""

    def test_fetch_with_mocked_client(self) -> None:
        """Should fetch and process region data."""
        mock_client = mock.MagicMock()

        # Mock stats response
        mock_client.get_region_stats.return_value = {"numChecklists": 1000}

        # Mock observations response
        mock_client.get_recent_observations.return_value = [
            {"speciesCode": "carwre", "comName": "Carolina Wren", "sciName": ""},
            {"speciesCode": "carwre", "comName": "Carolina Wren", "sciName": ""},
            {"speciesCode": "norcar", "comName": "Northern Cardinal", "sciName": ""},
        ]

        total_cl, species = fetch_region_data(
            mock_client, "US-NC-063", years=1, verbose=False
        )

        assert total_cl == 1000
        assert "carwre" in species
        assert "norcar" in species

    def test_handles_api_errors_gracefully(self) -> None:
        """Should handle API errors without crashing."""
        from bird_targets.ebird_client import EBirdAPIError

        mock_client = mock.MagicMock()
        mock_client.get_region_stats.side_effect = EBirdAPIError("API Error")
        mock_client.get_recent_observations.return_value = []

        # Should not raise
        total_cl, species = fetch_region_data(
            mock_client, "US-NC-063", years=1, verbose=False
        )

        assert total_cl == 0
        assert len(species) == 0
