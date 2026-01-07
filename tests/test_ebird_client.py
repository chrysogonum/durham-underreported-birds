"""Tests for the eBird API client module."""

import os
from unittest import mock

import pytest

from bird_targets.ebird_client import EBirdAPIError, EBirdClient, require_api_key


class TestEBirdClient:
    """Tests for EBirdClient class."""

    def test_init_with_api_key(self) -> None:
        """Should accept API key directly."""
        client = EBirdClient(api_key="test_key")
        assert client.api_key == "test_key"

    def test_init_from_env_var(self) -> None:
        """Should read API key from environment variable."""
        with mock.patch.dict(os.environ, {"EBIRD_API_KEY": "env_key"}):
            client = EBirdClient()
            assert client.api_key == "env_key"

    def test_init_no_key_raises_error(self) -> None:
        """Should raise error when no API key is available."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Remove EBIRD_API_KEY if it exists
            os.environ.pop("EBIRD_API_KEY", None)
            with pytest.raises(EBirdAPIError, match="No eBird API key"):
                EBirdClient()

    def test_request_adds_auth_header(self) -> None:
        """Should add API token header to requests."""
        client = EBirdClient(api_key="test_key")

        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'["species1", "species2"]'
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch("urllib.request.Request") as mock_request_class:
                mock_request = mock.MagicMock()
                mock_request_class.return_value = mock_request

                client.get_species_list("US-NC-063")

                mock_request.add_header.assert_called_with(
                    "X-eBirdApiToken", "test_key"
                )

    def test_get_species_list_returns_list(self) -> None:
        """Should return list of species codes."""
        client = EBirdClient(api_key="test_key")

        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'["carwre", "norcar", "blujay"]'
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            result = client.get_species_list("US-NC-063")

        assert result == ["carwre", "norcar", "blujay"]

    def test_get_region_stats_with_year_filter(self) -> None:
        """Should include year parameter in request."""
        client = EBirdClient(api_key="test_key")

        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'{"numChecklists": 1000}'
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch("urllib.request.Request") as mock_request_class:
                mock_request = mock.MagicMock()
                mock_request_class.return_value = mock_request

                client.get_region_stats("US-NC-063", year=2023)

                # Check URL contains year parameter
                call_args = mock_request_class.call_args
                url = call_args[0][0]
                assert "yr=2023" in url

    def test_get_recent_observations_limits_back_days(self) -> None:
        """Should limit back parameter to 30 days max."""
        client = EBirdClient(api_key="test_key")

        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"[]"
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch("urllib.request.Request") as mock_request_class:
                mock_request = mock.MagicMock()
                mock_request_class.return_value = mock_request

                # Request 100 days, should be limited to 30
                client.get_recent_observations("US-NC-063", back=100)

                call_args = mock_request_class.call_args
                url = call_args[0][0]
                assert "back=30" in url


class TestRequireApiKey:
    """Tests for require_api_key function."""

    def test_returns_key_when_set(self) -> None:
        """Should return API key when environment variable is set."""
        with mock.patch.dict(os.environ, {"EBIRD_API_KEY": "my_api_key"}):
            result = require_api_key()
            assert result == "my_api_key"

    def test_exits_when_not_set(self) -> None:
        """Should exit with error when API key is not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("EBIRD_API_KEY", None)
            with pytest.raises(SystemExit) as exc_info:
                require_api_key()
            assert exc_info.value.code == 1
