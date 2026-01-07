"""Tests for the export module."""

import json
import tempfile
from pathlib import Path

from bird_targets.__main__ import main
from bird_targets.export import (
    export_all,
    generate_checklist_density_geojson,
    generate_public_lands_geojson,
    generate_species_dossier,
    generate_survey_targets_geojson,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures"


class TestGeneratePublicLandsGeojson:
    """Tests for generate_public_lands_geojson function."""

    def test_returns_feature_collection(self) -> None:
        """Should return a valid GeoJSON FeatureCollection."""
        result = generate_public_lands_geojson(FIXTURES_PATH)

        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert len(result["features"]) > 0

    def test_features_have_required_properties(self) -> None:
        """Each feature should have name, type, and geometry."""
        result = generate_public_lands_geojson(FIXTURES_PATH)

        for feature in result["features"]:
            assert feature["type"] == "Feature"
            assert "name" in feature["properties"]
            assert "type" in feature["properties"]
            assert feature["geometry"]["type"] == "Polygon"


class TestGenerateChecklistDensityGeojson:
    """Tests for generate_checklist_density_geojson function."""

    def test_returns_feature_collection(self) -> None:
        """Should return a valid GeoJSON FeatureCollection."""
        result = generate_checklist_density_geojson(FIXTURES_PATH)

        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert len(result["features"]) > 0

    def test_features_are_points(self) -> None:
        """Each feature should be a Point geometry."""
        result = generate_checklist_density_geojson(FIXTURES_PATH)

        for feature in result["features"]:
            assert feature["geometry"]["type"] == "Point"

    def test_features_have_density_class(self) -> None:
        """Each feature should have a density_class property."""
        result = generate_checklist_density_geojson(FIXTURES_PATH)

        for feature in result["features"]:
            assert "density_class" in feature["properties"]
            assert feature["properties"]["density_class"] in ["high", "medium", "low"]


class TestGenerateSurveyTargetsGeojson:
    """Tests for generate_survey_targets_geojson function."""

    def test_returns_feature_collection(self) -> None:
        """Should return a valid GeoJSON FeatureCollection."""
        result = generate_survey_targets_geojson(FIXTURES_PATH)

        assert result["type"] == "FeatureCollection"
        assert "features" in result

    def test_features_have_survey_priority(self) -> None:
        """Each feature should have a survey_priority property."""
        result = generate_survey_targets_geojson(FIXTURES_PATH)

        for feature in result["features"]:
            assert "survey_priority" in feature["properties"]
            assert feature["properties"]["survey_priority"] in ["high", "medium", "low"]


class TestGenerateSpeciesDossier:
    """Tests for generate_species_dossier function."""

    def test_returns_markdown_content(self) -> None:
        """Should return markdown content with species info."""
        content = generate_species_dossier(
            species_code="woothr",
            common_name="Wood Thrush",
            expected_score=0.35,
            observed_score=0.16,
            underreported_score=0.19,
            fixtures_path=FIXTURES_PATH,
        )

        assert "# Wood Thrush" in content
        assert "woothr" in content
        assert "0.35" in content or "0.3500" in content

    def test_includes_regional_context(self) -> None:
        """Should include information about adjacent regions."""
        content = generate_species_dossier(
            species_code="woothr",
            common_name="Wood Thrush",
            expected_score=0.35,
            observed_score=0.16,
            underreported_score=0.19,
            fixtures_path=FIXTURES_PATH,
        )

        assert "Durham County" in content
        assert "Orange County" in content


class TestExportAll:
    """Tests for export_all function."""

    def test_creates_all_layers(self) -> None:
        """Should create all three GeoJSON layer files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            export_all(FIXTURES_PATH, out_path)

            layers_path = out_path / "layers"
            assert (layers_path / "public_lands.geojson").exists()
            assert (layers_path / "checklist_density.geojson").exists()
            assert (layers_path / "survey_targets.geojson").exists()

    def test_creates_species_dossiers(self) -> None:
        """Should create species dossier markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            export_all(FIXTURES_PATH, out_path)

            dossiers_path = out_path / "species_dossiers"
            md_files = list(dossiers_path.glob("*.md"))
            assert len(md_files) >= 3

    def test_returns_export_counts(self) -> None:
        """Should return counts of exported files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            result = export_all(FIXTURES_PATH, out_path)

            assert result["layers_exported"] == 3
            assert result["dossiers_exported"] >= 3

    def test_geojson_files_are_valid(self) -> None:
        """GeoJSON files should be valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            export_all(FIXTURES_PATH, out_path)

            layers_path = out_path / "layers"
            for geojson_file in layers_path.glob("*.geojson"):
                with open(geojson_file) as f:
                    data = json.load(f)
                    assert data["type"] == "FeatureCollection"


class TestExportCommand:
    """Tests for the export CLI command."""

    def test_export_creates_layers_directory(self) -> None:
        """Export command should create layers directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main(["export", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            assert result == 0
            assert (Path(tmpdir) / "layers").exists()

    def test_export_creates_dossiers_directory(self) -> None:
        """Export command should create species_dossiers directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main(["export", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            assert result == 0
            assert (Path(tmpdir) / "species_dossiers").exists()

    def test_export_invalid_fixtures_returns_error(self) -> None:
        """Export with invalid fixtures path should return error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main(
                ["export", "--fixtures", "/nonexistent/path", "--out", tmpdir]
            )

            assert result == 1

    def test_export_deterministic_output(self) -> None:
        """Running export twice should produce identical output."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                main(["export", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir1])
                main(["export", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir2])

                # Compare public_lands.geojson
                with open(Path(tmpdir1) / "layers" / "public_lands.geojson") as f1:
                    content1 = f1.read()
                with open(Path(tmpdir2) / "layers" / "public_lands.geojson") as f2:
                    content2 = f2.read()

                assert content1 == content2
