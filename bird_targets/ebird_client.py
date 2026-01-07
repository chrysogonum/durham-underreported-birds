"""eBird API client wrapper.

This module provides a client for interacting with the eBird API 2.0.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class EBirdAPIError(Exception):
    """Exception raised for eBird API errors."""

    pass


class EBirdClient:
    """Client for eBird API 2.0.

    Provides methods to fetch observation data, species lists, and regional
    statistics from the eBird API.
    """

    BASE_URL = "https://api.ebird.org/v2"
    RATE_LIMIT_DELAY = 0.5  # Seconds between requests

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the eBird client.

        Args:
            api_key: eBird API key. If not provided, reads from EBIRD_API_KEY.

        Raises:
            EBirdAPIError: If no API key is available.
        """
        self.api_key = api_key or os.environ.get("EBIRD_API_KEY")
        if not self.api_key:
            raise EBirdAPIError(
                "No eBird API key provided. Set EBIRD_API_KEY environment variable."
            )
        self._last_request_time: float = 0

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _request(self, endpoint: str, params: dict | None = None) -> Any:
        """Make a request to the eBird API.

        Args:
            endpoint: API endpoint (without base URL)
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            EBirdAPIError: If the request fails
        """
        self._rate_limit()

        url = f"{self.BASE_URL}{endpoint}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            url = f"{url}?{query}"

        request = urllib.request.Request(url)
        request.add_header("X-eBirdApiToken", self.api_key)

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise EBirdAPIError(f"HTTP {e.code}: {e.reason} for {url}") from e
        except urllib.error.URLError as e:
            raise EBirdAPIError(f"Request failed: {e.reason}") from e

    def get_region_info(self, region_code: str) -> dict[str, Any]:
        """Get information about a region.

        Args:
            region_code: eBird region code (e.g., 'US-NC-063')

        Returns:
            Region information dictionary
        """
        return self._request(f"/ref/region/info/{region_code}")

    def get_adjacent_regions(self, region_code: str) -> list[dict[str, Any]]:
        """Get adjacent regions for a given region code.

        Args:
            region_code: eBird region code (e.g., 'US-NC-063')

        Returns:
            List of adjacent region dictionaries
        """
        return self._request(f"/ref/adjacent/{region_code}")

    def get_species_list(self, region_code: str) -> list[str]:
        """Get species list for a region.

        Args:
            region_code: eBird region code

        Returns:
            List of species codes
        """
        return self._request(f"/product/spplist/{region_code}")

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
        return self._request(
            f"/data/obs/{region_code}/recent",
            params={"back": min(back, 30)},
        )

    def get_historic_observations(
        self,
        region_code: str,
        year: int,
        month: int,
        day: int,
    ) -> list[dict[str, Any]]:
        """Get historic observations for a specific date.

        Args:
            region_code: eBird region code
            year: Year
            month: Month (1-12)
            day: Day (1-31)

        Returns:
            List of observation dictionaries
        """
        return self._request(f"/data/obs/{region_code}/historic/{year}/{month}/{day}")

    def get_region_stats(
        self,
        region_code: str,
        year: int | None = None,
        month: int | None = None,
    ) -> dict[str, Any]:
        """Get regional statistics including checklist counts.

        Args:
            region_code: eBird region code
            year: Optional year filter
            month: Optional month filter (1-12)

        Returns:
            Statistics dictionary with numChecklists, numSpecies, etc.
        """
        params = {}
        if year:
            params["yr"] = year
        if month:
            params["m"] = month
        return self._request(f"/product/stats/{region_code}", params or None)

    def get_top_100(
        self,
        region_code: str,
        year: int | None = None,
        rank_by: str = "spp",
    ) -> list[dict[str, Any]]:
        """Get top 100 contributors for a region.

        Args:
            region_code: eBird region code
            year: Optional year filter
            rank_by: Ranking criteria ('spp' for species, 'cl' for checklists)

        Returns:
            List of contributor dictionaries
        """
        params = {"rankBy": rank_by}
        if year:
            params["yr"] = year
        return self._request(f"/product/top100/{region_code}", params)

    def get_checklist_feed(
        self,
        region_code: str,
        year: int,
        month: int,
        day: int,
        max_results: int = 200,
    ) -> list[dict[str, Any]]:
        """Get checklist feed for a specific date.

        Args:
            region_code: eBird region code
            year: Year
            month: Month (1-12)
            day: Day (1-31)
            max_results: Maximum number of results

        Returns:
            List of checklist summary dictionaries
        """
        return self._request(
            f"/product/lists/{region_code}/{year}/{month}/{day}",
            params={"maxResults": max_results},
        )


def require_api_key() -> str:
    """Check for API key and exit with error if not found.

    Returns:
        The API key if found

    Raises:
        SystemExit: If API key is not set
    """
    api_key = os.environ.get("EBIRD_API_KEY")
    if not api_key:
        print(
            "Error: EBIRD_API_KEY environment variable not set.",
            file=sys.stderr,
        )
        print(
            "Get an API key from https://ebird.org/api/keygen",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key
