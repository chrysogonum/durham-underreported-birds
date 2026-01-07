"""eBird API client wrapper.

This module provides a client for interacting with the eBird API.
For testing and demo purposes, use fixtures instead of making live API calls.
"""

from __future__ import annotations

import os
from typing import Any


class EBirdClient:
    """Client for eBird API 2.0.

    In production, this client makes real API calls. For tests and demos,
    use fixture data directly instead of instantiating this client.
    """

    BASE_URL = "https://api.ebird.org/v2"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the eBird client.

        Args:
            api_key: eBird API key. If not provided, reads from EBIRD_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("EBIRD_API_KEY")

    def get_adjacent_regions(self, region_code: str) -> list[dict[str, Any]]:
        """Get adjacent regions for a given region code.

        Args:
            region_code: eBird region code (e.g., 'US-NC-063' for Durham County)

        Returns:
            List of adjacent region dictionaries
        """
        # Placeholder - would call /ref/geo/adjacent/{regionCode}
        raise NotImplementedError("Use fixtures for offline/demo mode")

    def get_species_list(self, region_code: str) -> list[str]:
        """Get species list for a region.

        Args:
            region_code: eBird region code

        Returns:
            List of species codes
        """
        # Placeholder - would call /product/spplist/{regionCode}
        raise NotImplementedError("Use fixtures for offline/demo mode")

    def get_recent_observations(
        self,
        region_code: str,
        back: int = 30,
    ) -> list[dict[str, Any]]:
        """Get recent observations for a region.

        Args:
            region_code: eBird region code
            back: Number of days back to search (max 30)

        Returns:
            List of observation dictionaries
        """
        # Placeholder - would call /data/obs/{regionCode}/recent
        raise NotImplementedError("Use fixtures for offline/demo mode")
