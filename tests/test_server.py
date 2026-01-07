"""Tests for the server module."""

import json
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from bird_targets.__main__ import main as cli_main
from bird_targets.export import export_all
from bird_targets.server import (
    AVAILABLE_LAYERS,
    get_index_html,
    is_port_available,
    run_server,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures"


class TestGetIndexHtml:
    """Tests for get_index_html function."""

    def test_returns_html_string(self) -> None:
        """Should return a non-empty HTML string."""
        html = get_index_html()

        assert isinstance(html, str)
        assert len(html) > 0

    def test_contains_doctype(self) -> None:
        """Should contain HTML5 doctype."""
        html = get_index_html()

        assert "<!DOCTYPE html>" in html

    def test_contains_leaflet_references(self) -> None:
        """Should include Leaflet CSS and JS."""
        html = get_index_html()

        assert "leaflet.css" in html
        assert "leaflet.js" in html

    def test_contains_layer_toggles(self) -> None:
        """Should include checkboxes for layer toggles."""
        html = get_index_html()

        assert "toggle-public-lands" in html
        assert "toggle-checklist-density" in html
        assert "toggle-survey-targets" in html

    def test_contains_map_container(self) -> None:
        """Should include map div container."""
        html = get_index_html()

        assert 'id="map"' in html

    def test_contains_sidebar(self) -> None:
        """Should include sidebar for bird list."""
        html = get_index_html()

        assert "sidebar" in html
        assert "bird-list" in html

    def test_contains_month_filter(self) -> None:
        """Should include month filter dropdown."""
        html = get_index_html()

        assert "month-filter" in html
        assert "January" in html
        assert "December" in html

    def test_contains_detail_panel(self) -> None:
        """Should include detail panel for dossiers."""
        html = get_index_html()

        assert "detail-panel" in html
        assert "detail-content" in html

    def test_uses_event_delegation_for_bird_clicks(self) -> None:
        """Should use event delegation for bird item clicks (Safari compatibility)."""
        html = get_index_html()

        # Should use addEventListener on bird-list for click events
        assert "bird-list" in html
        assert "addEventListener" in html
        assert ".closest('.bird-item')" in html

    def test_bird_items_have_data_attributes(self) -> None:
        """Should set data-species attribute on bird items for event delegation."""
        html = get_index_html()

        # Should set data-species attribute in renderBirdList
        assert "data-species" in html
        assert "getAttribute('data-species')" in html


class TestAvailableLayers:
    """Tests for AVAILABLE_LAYERS constant."""

    def test_contains_expected_layers(self) -> None:
        """Should contain all three expected layers."""
        assert "public_lands" in AVAILABLE_LAYERS
        assert "checklist_density" in AVAILABLE_LAYERS
        assert "survey_targets" in AVAILABLE_LAYERS

    def test_has_three_layers(self) -> None:
        """Should have exactly three layers."""
        assert len(AVAILABLE_LAYERS) == 3


class TestIsPortAvailable:
    """Tests for is_port_available function."""

    def test_high_port_is_available(self) -> None:
        """A high random port should typically be available."""
        # Use a high port that's unlikely to be in use
        assert is_port_available(59999) is True


class TestServerEndpoints:
    """Integration tests for server HTTP endpoints."""

    @classmethod
    def setup_class(cls) -> None:
        """Set up test fixtures and start server."""
        cls.tmpdir = tempfile.mkdtemp()
        cls.out_path = Path(cls.tmpdir)

        # Run demo to create targets_ranked.csv
        cli_main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", str(cls.out_path)])

        # Export layers and dossiers to temp directory
        export_all(FIXTURES_PATH, cls.out_path)

        # Find an available port
        cls.port = 18765
        while not is_port_available(cls.port):
            cls.port += 1

        # Start server in background thread (pass out_path, not layers_path)
        cls.server = run_server(
            cls.out_path,
            port=cls.port,
            quiet=True,
        )
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

        # Give server time to start
        time.sleep(0.1)

    @classmethod
    def teardown_class(cls) -> None:
        """Shut down server."""
        cls.server.shutdown()
        cls.server_thread.join(timeout=1)

    def test_root_returns_html(self) -> None:
        """GET / should return HTML."""
        url = f"http://localhost:{self.port}/"
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")

            assert response.status == 200
            assert "<!DOCTYPE html>" in content

    def test_layers_returns_json_list(self) -> None:
        """GET /layers should return JSON list of layer names."""
        url = f"http://localhost:{self.port}/layers"
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)

            assert response.status == 200
            assert isinstance(data, list)
            assert "public_lands" in data
            assert "checklist_density" in data
            assert "survey_targets" in data

    def test_public_lands_layer_returns_geojson(self) -> None:
        """GET /layers/public_lands should return GeoJSON."""
        url = f"http://localhost:{self.port}/layers/public_lands"
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)

            assert response.status == 200
            assert data["type"] == "FeatureCollection"
            assert "features" in data

    def test_checklist_density_layer_returns_geojson(self) -> None:
        """GET /layers/checklist_density should return GeoJSON."""
        url = f"http://localhost:{self.port}/layers/checklist_density"
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)

            assert response.status == 200
            assert data["type"] == "FeatureCollection"

    def test_survey_targets_layer_returns_geojson(self) -> None:
        """GET /layers/survey_targets should return GeoJSON."""
        url = f"http://localhost:{self.port}/layers/survey_targets"
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)

            assert response.status == 200
            assert data["type"] == "FeatureCollection"

    def test_unknown_layer_returns_404(self) -> None:
        """GET /layers/unknown should return 404."""
        url = f"http://localhost:{self.port}/layers/unknown"
        try:
            urllib.request.urlopen(url)
            assert False, "Expected 404 error"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_unknown_path_returns_404(self) -> None:
        """GET /unknown should return 404."""
        url = f"http://localhost:{self.port}/unknown"
        try:
            urllib.request.urlopen(url)
            assert False, "Expected 404 error"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_targets_returns_json_list(self) -> None:
        """GET /targets should return JSON list of target species."""
        url = f"http://localhost:{self.port}/targets"
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)

            assert response.status == 200
            assert isinstance(data, list)
            assert len(data) > 0
            # Check structure of first item
            first = data[0]
            assert "species_code" in first
            assert "common_name" in first
            assert "underreported_score" in first
            assert "best_months" in first

    def test_targets_sorted_by_score(self) -> None:
        """GET /targets should return species sorted by underreported_score."""
        url = f"http://localhost:{self.port}/targets"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode("utf-8"))

            scores = [t["underreported_score"] for t in data]
            assert scores == sorted(scores, reverse=True)

    def test_dossier_returns_markdown(self) -> None:
        """GET /dossiers/{species_code} should return markdown content."""
        # First get targets to find a valid species code
        url = f"http://localhost:{self.port}/targets"
        with urllib.request.urlopen(url) as response:
            targets = json.loads(response.read().decode("utf-8"))

        # Find a species that has a dossier (underreported_score > 0)
        species_with_dossier = None
        for t in targets:
            if t["underreported_score"] > 0:
                species_with_dossier = t["species_code"]
                break

        if species_with_dossier:
            url = f"http://localhost:{self.port}/dossiers/{species_with_dossier}"
            with urllib.request.urlopen(url) as response:
                content = response.read().decode("utf-8")

                assert response.status == 200
                assert "#" in content  # Markdown headers

    def test_dossier_missing_returns_404(self) -> None:
        """GET /dossiers/nonexistent should return 404."""
        url = f"http://localhost:{self.port}/dossiers/nonexistent_species"
        try:
            urllib.request.urlopen(url)
            assert False, "Expected 404 error"
        except urllib.error.HTTPError as e:
            assert e.code == 404
