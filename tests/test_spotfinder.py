"""Tests for the spotfinder module."""

import json
from pathlib import Path

import pytest

from bird_targets.scoring import SpeciesScore
from bird_targets.spotfinder import (
    export_spot_guides,
    generate_species_spots_geojson,
    generate_spot_guide,
    load_habitat_rules,
    load_osm_trails,
    load_species_spots,
)


@pytest.fixture
def fixtures_path():
    """Return the path to test fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_species_spots():
    """Return sample species spots data."""
    return {
        "woothr": {
            "habitat_specific": "Interior deciduous forest with dense understory",
            "time_of_day": "dawn, morning",
            "detection_tips": "Listen for flute-like song at dawn",
            "spots": [
                {
                    "place_name": "Duke Forest - Test Area",
                    "public_land": "Duke Forest",
                    "trailhead": "Test Trailhead",
                    "why_here": "Good habitat",
                    "coordinates": [-79.0, 36.0],
                    "confidence": 0.85,
                }
            ],
        }
    }


@pytest.fixture
def sample_habitat_rules():
    """Return sample habitat rules."""
    return {
        "woothr": {
            "common_name": "Wood Thrush",
            "habitats": ["mature_forest", "riparian"],
            "seasonality": ["breeding"],
            "weight": 0.8,
            "notes": "Wood Thrush - interior forest, declining",
        }
    }


@pytest.fixture
def sample_trails_data():
    """Return sample OSM trails data."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Test Trailhead",
                    "type": "trailhead",
                    "parking": True,
                    "parking_spaces": 20,
                },
                "geometry": {"type": "Point", "coordinates": [-79.0, 36.0]},
            }
        ],
    }


@pytest.fixture
def sample_scores():
    """Return sample species scores."""
    return [
        SpeciesScore(
            species_code="woothr",
            common_name="Wood Thrush",
            observer_expected_score=0.1,
            habitat_expected_score=0.05,
            expected_score=0.08,
            observed_score=0.01,
            underreported_score=0.07,
            habitat_rationale="Forest habitat available",
        ),
        SpeciesScore(
            species_code="kenwar",
            common_name="Kentucky Warbler",
            observer_expected_score=0.12,
            habitat_expected_score=0.04,
            expected_score=0.09,
            observed_score=0.005,
            underreported_score=0.085,
            habitat_rationale="Riparian habitat available",
        ),
    ]


class TestLoadSpeciesSpots:
    """Tests for load_species_spots function."""

    def test_loads_existing_file(self, fixtures_path):
        """Should load species spots from fixtures."""
        spots = load_species_spots(fixtures_path)
        assert isinstance(spots, dict)
        # Should have some species data
        assert len(spots) > 0

    def test_returns_empty_dict_if_missing(self, tmp_path):
        """Should return empty dict if file doesn't exist."""
        spots = load_species_spots(tmp_path)
        assert spots == {}


class TestLoadOsmTrails:
    """Tests for load_osm_trails function."""

    def test_loads_existing_file(self, fixtures_path):
        """Should load OSM trails from fixtures."""
        trails = load_osm_trails(fixtures_path)
        assert trails["type"] == "FeatureCollection"
        assert "features" in trails
        assert len(trails["features"]) > 0

    def test_returns_empty_collection_if_missing(self, tmp_path):
        """Should return empty FeatureCollection if file doesn't exist."""
        trails = load_osm_trails(tmp_path)
        assert trails["type"] == "FeatureCollection"
        assert trails["features"] == []


class TestLoadHabitatRules:
    """Tests for load_habitat_rules function."""

    def test_loads_default_rules(self):
        """Should load habitat rules from default location."""
        rules = load_habitat_rules()
        assert isinstance(rules, dict)


class TestGenerateSpotGuide:
    """Tests for generate_spot_guide function."""

    def test_generates_markdown(
        self, sample_species_spots, sample_habitat_rules, sample_trails_data
    ):
        """Should generate valid markdown content."""
        guide = generate_spot_guide(
            species_code="woothr",
            common_name="Wood Thrush",
            species_spots=sample_species_spots,
            habitat_rules=sample_habitat_rules,
            trails_data=sample_trails_data,
        )

        assert "# Wood Thrush - Spot Guide" in guide
        assert "## What Habitat Exactly" in guide
        assert "## Where to Look in Durham" in guide
        assert "## When to Survey" in guide
        assert "## How to Detect" in guide

    def test_includes_spot_details(
        self, sample_species_spots, sample_habitat_rules, sample_trails_data
    ):
        """Should include spot-specific details."""
        guide = generate_spot_guide(
            species_code="woothr",
            common_name="Wood Thrush",
            species_spots=sample_species_spots,
            habitat_rules=sample_habitat_rules,
            trails_data=sample_trails_data,
        )

        assert "Duke Forest - Test Area" in guide
        assert "Test Trailhead" in guide
        assert "parking available" in guide
        assert "Confidence:" in guide

    def test_includes_detection_tips(
        self, sample_species_spots, sample_habitat_rules, sample_trails_data
    ):
        """Should include detection tips."""
        guide = generate_spot_guide(
            species_code="woothr",
            common_name="Wood Thrush",
            species_spots=sample_species_spots,
            habitat_rules=sample_habitat_rules,
            trails_data=sample_trails_data,
        )

        assert "Listen for flute-like song" in guide

    def test_handles_missing_species(
        self, sample_species_spots, sample_habitat_rules, sample_trails_data
    ):
        """Should generate guide even for species without spot data."""
        guide = generate_spot_guide(
            species_code="missing",
            common_name="Missing Species",
            species_spots=sample_species_spots,
            habitat_rules=sample_habitat_rules,
            trails_data=sample_trails_data,
        )

        assert "# Missing Species - Spot Guide" in guide
        assert "No specific spot recommendations" in guide


class TestGenerateSpeciesSpotsGeojson:
    """Tests for generate_species_spots_geojson function."""

    def test_generates_valid_geojson(self, sample_scores, sample_species_spots):
        """Should generate valid GeoJSON FeatureCollection."""
        geojson = generate_species_spots_geojson(sample_scores, sample_species_spots)

        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson

    def test_includes_required_properties(self, sample_scores, sample_species_spots):
        """Should include required properties in features."""
        geojson = generate_species_spots_geojson(sample_scores, sample_species_spots)

        for feature in geojson["features"]:
            props = feature["properties"]
            assert "species_code" in props
            assert "place_name" in props
            assert "why_here" in props
            assert "confidence" in props

    def test_only_includes_underreported_species(self, sample_species_spots):
        """Should only include species with positive underreported score."""
        scores_with_zero = [
            SpeciesScore(
                species_code="woothr",
                common_name="Wood Thrush",
                observer_expected_score=0.1,
                habitat_expected_score=0.05,
                expected_score=0.08,
                observed_score=0.08,
                underreported_score=0.0,  # Zero score
                habitat_rationale="",
            ),
        ]
        geojson = generate_species_spots_geojson(scores_with_zero, sample_species_spots)

        assert len(geojson["features"]) == 0

    def test_sorts_by_underreported_score(self, sample_scores, sample_species_spots):
        """Should sort features by underreported score descending."""
        # Need spots data for both species to get features
        spots = {
            "woothr": sample_species_spots["woothr"],
            "kenwar": {
                "habitat_specific": "Moist ravines",
                "spots": [
                    {
                        "place_name": "Test Spot",
                        "coordinates": [-79.0, 36.0],
                        "confidence": 0.8,
                    }
                ],
            },
        }
        geojson = generate_species_spots_geojson(sample_scores, spots)

        if len(geojson["features"]) >= 2:
            # First feature should have higher underreported score
            first_score = geojson["features"][0]["properties"]["underreported_score"]
            second_score = geojson["features"][1]["properties"]["underreported_score"]
            assert first_score >= second_score


class TestExportSpotGuides:
    """Tests for export_spot_guides function."""

    def test_creates_spot_guides_directory(
        self, fixtures_path, sample_scores, tmp_path
    ):
        """Should create spot_guides directory."""
        export_spot_guides(fixtures_path, tmp_path, sample_scores)

        guides_dir = tmp_path / "spot_guides"
        assert guides_dir.exists()
        assert guides_dir.is_dir()

    def test_creates_species_spots_geojson(
        self, fixtures_path, sample_scores, tmp_path
    ):
        """Should create species_spots.geojson."""
        export_spot_guides(fixtures_path, tmp_path, sample_scores)

        geojson_file = tmp_path / "layers" / "species_spots.geojson"
        assert geojson_file.exists()

        # Verify it's valid JSON
        with open(geojson_file) as f:
            data = json.load(f)
        assert data["type"] == "FeatureCollection"

    def test_returns_export_counts(self, fixtures_path, sample_scores, tmp_path):
        """Should return counts of exported files."""
        result = export_spot_guides(fixtures_path, tmp_path, sample_scores)

        assert "spot_guides_exported" in result
        assert "species_spots_features" in result
        assert isinstance(result["spot_guides_exported"], int)
        assert isinstance(result["species_spots_features"], int)

    def test_exports_correct_number_of_guides(
        self, fixtures_path, sample_scores, tmp_path
    ):
        """Should export guides for underreported species."""
        result = export_spot_guides(fixtures_path, tmp_path, sample_scores)

        guides_dir = tmp_path / "spot_guides"
        md_files = list(guides_dir.glob("*.md"))

        assert len(md_files) == result["spot_guides_exported"]
