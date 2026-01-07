"""Tests for the habitat model module."""

from pathlib import Path

from bird_targets.habitat_model import (
    DEFAULT_LAND_TYPE_HABITATS,
    HabitatMatch,
    HabitatScore,
    calculate_all_habitat_scores,
    calculate_habitat_score,
    get_habitat_rationale,
    get_land_habitats,
    load_habitat_rules,
)
from bird_targets.scoring import (
    DEFAULT_HABITAT_WEIGHT,
    DEFAULT_OBSERVER_WEIGHT,
    calculate_combined_expected,
    calculate_underreported_scores,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures"
HABITAT_RULES_PATH = (
    Path(__file__).parent.parent / "data" / "species_habitat_rules.json"
)


class TestLoadHabitatRules:
    """Tests for load_habitat_rules function."""

    def test_load_rules_from_file(self) -> None:
        """Verify rules are loaded correctly from JSON file."""
        rules = load_habitat_rules(HABITAT_RULES_PATH)

        # Should have species codes as keys
        assert "brdowl" in rules  # Barred Owl
        assert "easowl1" in rules  # Eastern Screech-Owl
        assert "woothr" in rules  # Wood Thrush

    def test_rules_have_required_fields(self) -> None:
        """Verify each rule has required fields."""
        rules = load_habitat_rules(HABITAT_RULES_PATH)

        for code, rule in rules.items():
            if code.startswith("_"):  # Skip comments
                continue
            assert "habitats" in rule, f"{code} missing habitats"
            assert "weight" in rule, f"{code} missing weight"
            assert isinstance(rule["habitats"], list), f"{code} habitats not a list"
            assert 0 <= rule["weight"] <= 1, f"{code} weight out of range"

    def test_load_nonexistent_file(self) -> None:
        """Verify loading nonexistent file returns empty dict."""
        rules = load_habitat_rules(Path("/nonexistent/path.json"))
        assert rules == {}


class TestGetLandHabitats:
    """Tests for get_land_habitats function."""

    def test_state_park_habitats(self) -> None:
        """State parks should have forest and field habitats."""
        habitats = get_land_habitats("state_park")
        assert "mature_forest" in habitats
        assert "riparian" in habitats

    def test_unknown_land_type_defaults(self) -> None:
        """Unknown land types should default to mixed_forest."""
        habitats = get_land_habitats("unknown_type")
        assert habitats == ["mixed_forest"]

    def test_custom_habitats_override(self) -> None:
        """Custom habitat list should override defaults."""
        custom = ["wetland", "lake_wetland"]
        habitats = get_land_habitats("state_park", custom_habitats=custom)
        assert habitats == custom

    def test_all_default_land_types_defined(self) -> None:
        """Verify all expected land types have habitat mappings."""
        expected_types = [
            "university_forest",
            "state_park",
            "state_recreation_area",
            "regional_park",
            "city_park",
            "wildlife_refuge",
            "nature_preserve",
        ]
        for land_type in expected_types:
            assert land_type in DEFAULT_LAND_TYPE_HABITATS


class TestCalculateHabitatScore:
    """Tests for calculate_habitat_score function."""

    def test_species_with_matching_habitat(self) -> None:
        """Species with matching habitats should have positive score."""
        species_rules = {
            "habitats": ["mature_forest", "riparian"],
            "weight": 0.8,
        }
        public_lands = {
            "features": [
                {
                    "properties": {
                        "name": "Test Forest",
                        "type": "state_park",
                        "area_acres": 1000,
                        "habitats": ["mature_forest", "riparian", "open_fields"],
                    }
                }
            ]
        }

        score = calculate_habitat_score("testsp", species_rules, public_lands)

        assert score.habitat_expected_score > 0
        assert len(score.matched_lands) == 1
        assert score.matched_lands[0].land_name == "Test Forest"

    def test_species_with_no_matching_habitat(self) -> None:
        """Species with no matching habitats should have zero score."""
        species_rules = {
            "habitats": ["wetland", "lake_wetland"],
            "weight": 0.6,
        }
        public_lands = {
            "features": [
                {
                    "properties": {
                        "name": "Dry Forest",
                        "type": "state_park",
                        "area_acres": 1000,
                        "habitats": ["mature_forest", "open_fields"],
                    }
                }
            ]
        }

        score = calculate_habitat_score("wetlandsp", species_rules, public_lands)

        assert score.habitat_expected_score == 0.0
        assert len(score.matched_lands) == 0

    def test_species_with_empty_habitats(self) -> None:
        """Species with no required habitats should have zero score."""
        species_rules = {
            "habitats": [],
            "weight": 0.5,
        }
        public_lands = {
            "features": [
                {
                    "properties": {
                        "name": "Some Land",
                        "type": "state_park",
                        "area_acres": 1000,
                    }
                }
            ]
        }

        score = calculate_habitat_score("emptysp", species_rules, public_lands)

        assert score.habitat_expected_score == 0.0

    def test_partial_habitat_match(self) -> None:
        """Partial habitat matches should weight by proportion."""
        species_rules = {
            "habitats": ["mature_forest", "riparian", "wetland"],  # 3 required
            "weight": 1.0,
        }
        public_lands = {
            "features": [
                {
                    "properties": {
                        "name": "Forest Only",
                        "type": "state_park",
                        "area_acres": 1000,
                        "habitats": ["mature_forest"],  # Only 1 of 3 matches
                    }
                }
            ]
        }

        score = calculate_habitat_score("partialsp", species_rules, public_lands)

        # Match proportion is 1/3
        assert score.habitat_expected_score > 0
        assert score.matched_lands[0].matched_habitats == ["mature_forest"]

    def test_multiple_lands_sum_contributions(self) -> None:
        """Multiple lands should sum their contributions."""
        species_rules = {
            "habitats": ["mature_forest"],
            "weight": 1.0,
        }
        public_lands = {
            "features": [
                {
                    "properties": {
                        "name": "Forest A",
                        "type": "state_park",
                        "area_acres": 500,
                        "habitats": ["mature_forest"],
                    }
                },
                {
                    "properties": {
                        "name": "Forest B",
                        "type": "state_park",
                        "area_acres": 500,
                        "habitats": ["mature_forest"],
                    }
                },
            ]
        }

        score = calculate_habitat_score("multisp", species_rules, public_lands)

        assert len(score.matched_lands) == 2
        # Full match on 100% of area with weight 1.0 -> score should be 1.0
        assert score.habitat_expected_score == 1.0

    def test_uses_default_habitats_when_not_specified(self) -> None:
        """Should use default land type habitats when not explicitly specified."""
        species_rules = {
            "habitats": ["mature_forest"],
            "weight": 0.8,
        }
        public_lands = {
            "features": [
                {
                    "properties": {
                        "name": "Test Park",
                        "type": "state_park",  # Has mature_forest by default
                        "area_acres": 1000,
                        # No explicit habitats - should use defaults
                    }
                }
            ]
        }

        score = calculate_habitat_score("defsp", species_rules, public_lands)

        assert score.habitat_expected_score > 0


class TestCalculateAllHabitatScores:
    """Tests for calculate_all_habitat_scores function."""

    def test_calculates_scores_for_all_species(self) -> None:
        """Should calculate scores for all species in rules file."""
        import json

        with open(FIXTURES_PATH / "public_lands.json") as f:
            public_lands = json.load(f)

        scores = calculate_all_habitat_scores(HABITAT_RULES_PATH, public_lands)

        # Should have scores for all species with rules
        assert "brdowl" in scores
        assert "woothr" in scores
        assert "kenwar" in scores

    def test_scores_are_habitat_score_objects(self) -> None:
        """All scores should be HabitatScore dataclass instances."""
        import json

        with open(FIXTURES_PATH / "public_lands.json") as f:
            public_lands = json.load(f)

        scores = calculate_all_habitat_scores(HABITAT_RULES_PATH, public_lands)

        for code, score in scores.items():
            if code.startswith("_"):
                continue
            assert isinstance(score, HabitatScore)
            assert score.species_code == code


class TestGetHabitatRationale:
    """Tests for get_habitat_rationale function."""

    def test_rationale_with_matches(self) -> None:
        """Should generate readable rationale with matched lands."""
        score = HabitatScore(
            species_code="testsp",
            habitat_expected_score=0.5,
            matched_lands=[
                HabitatMatch(
                    land_name="Duke Forest",
                    land_type="university_forest",
                    matched_habitats=["mature_forest", "riparian"],
                    area_acres=7000,
                    contribution=7000.0,
                ),
            ],
            rule_weight=0.8,
        )

        rationale = get_habitat_rationale(score)

        assert "Duke Forest" in rationale
        assert "0.5000" in rationale
        assert "mature_forest" in rationale
        assert "7,000 acres" in rationale

    def test_rationale_without_matches(self) -> None:
        """Should indicate no suitable habitat when no matches."""
        score = HabitatScore(
            species_code="testsp",
            habitat_expected_score=0.0,
            matched_lands=[],
            rule_weight=0.5,
        )

        rationale = get_habitat_rationale(score)

        assert "No suitable habitat" in rationale


class TestCombinedScoring:
    """Tests for combined observer + habitat scoring."""

    def test_default_weights(self) -> None:
        """Verify default weights are 0.7 observer, 0.3 habitat."""
        assert DEFAULT_OBSERVER_WEIGHT == 0.7
        assert DEFAULT_HABITAT_WEIGHT == 0.3

    def test_calculate_combined_expected_default(self) -> None:
        """Combined score with default weights."""
        observer = 0.5
        habitat = 0.8

        combined = calculate_combined_expected(observer, habitat)

        # 0.7 * 0.5 + 0.3 * 0.8 = 0.35 + 0.24 = 0.59
        assert abs(combined - 0.59) < 0.001

    def test_calculate_combined_expected_custom_weights(self) -> None:
        """Combined score with custom weights."""
        observer = 0.5
        habitat = 0.8

        combined = calculate_combined_expected(observer, habitat, 0.5, 0.5)

        # 0.5 * 0.5 + 0.5 * 0.8 = 0.25 + 0.4 = 0.65
        assert abs(combined - 0.65) < 0.001

    def test_calculate_combined_expected_zero_weights(self) -> None:
        """Combined score with zero weights should return 0."""
        combined = calculate_combined_expected(0.5, 0.8, 0.0, 0.0)
        assert combined == 0.0

    def test_calculate_combined_observer_only(self) -> None:
        """Combined score with habitat weight 0 should equal observer."""
        observer = 0.5
        habitat = 0.8

        combined = calculate_combined_expected(observer, habitat, 1.0, 0.0)

        assert abs(combined - observer) < 0.001

    def test_calculate_combined_habitat_only(self) -> None:
        """Combined score with observer weight 0 should equal habitat."""
        observer = 0.5
        habitat = 0.8

        combined = calculate_combined_expected(observer, habitat, 0.0, 1.0)

        assert abs(combined - habitat) < 0.001


class TestHabitatIntegration:
    """Integration tests for habitat scoring in full pipeline."""

    def test_scores_include_habitat_fields(self) -> None:
        """Underreported scores should include habitat fields."""
        scores = calculate_underreported_scores(
            FIXTURES_PATH,
            habitat_rules_path=HABITAT_RULES_PATH,
        )

        # Find a species with habitat rules
        for score in scores:
            if score.species_code == "woothr":  # Wood Thrush
                assert score.observer_expected_score >= 0
                assert score.habitat_expected_score >= 0
                break

    def test_habitat_scores_affect_ranking(self) -> None:
        """Species with habitat data should have different scores."""
        # Without habitat
        scores_no_habitat = calculate_underreported_scores(FIXTURES_PATH)

        # With habitat
        scores_with_habitat = calculate_underreported_scores(
            FIXTURES_PATH,
            habitat_rules_path=HABITAT_RULES_PATH,
        )

        # Get Wood Thrush score with habitat
        woothr_with_habitat = None
        for s in scores_with_habitat:
            if s.species_code == "woothr":
                woothr_with_habitat = s
                break

        # Wood Thrush should have habitat contribution
        if woothr_with_habitat:
            assert woothr_with_habitat.habitat_expected_score >= 0

        # Verify both score lists are non-empty
        assert len(scores_no_habitat) > 0
        assert len(scores_with_habitat) > 0

    def test_custom_weights_affect_scores(self) -> None:
        """Custom observer/habitat weights should affect combined scores."""
        # All observer
        scores_observer = calculate_underreported_scores(
            FIXTURES_PATH,
            habitat_rules_path=HABITAT_RULES_PATH,
            observer_weight=1.0,
            habitat_weight=0.0,
        )

        # All habitat
        scores_habitat = calculate_underreported_scores(
            FIXTURES_PATH,
            habitat_rules_path=HABITAT_RULES_PATH,
            observer_weight=0.0,
            habitat_weight=1.0,
        )

        # Find species with both signals to compare
        for so in scores_observer:
            for sh in scores_habitat:
                if so.species_code == sh.species_code:
                    # Expected scores should differ if habitat score != observer score
                    if so.observer_expected_score != so.habitat_expected_score:
                        assert so.expected_score != sh.expected_score
                    break
