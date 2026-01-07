"""Tests for the scoring module."""

from pathlib import Path

from bird_targets.scoring import (
    SpeciesScore,
    calculate_expected_score,
    calculate_observed_score,
    calculate_underreported_scores,
    load_fixtures,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures"


class TestLoadFixtures:
    """Tests for load_fixtures function."""

    def test_load_fixtures_returns_all_data(self) -> None:
        """Verify load_fixtures returns all required data structures."""
        regions, durham, adjacent, exclusions = load_fixtures(FIXTURES_PATH)

        assert "target_region" in regions
        assert "adjacent_regions" in regions
        assert regions["target_region"]["code"] == "US-NC-063"

        assert "species" in durham
        assert durham["checklists_total"] > 0

        assert "regions" in adjacent
        assert len(adjacent["regions"]) > 0

        assert "excluded_species" in exclusions


class TestCalculateExpectedScore:
    """Tests for calculate_expected_score function."""

    def test_species_in_all_adjacent(self) -> None:
        """Species present in all adjacent counties should have high expected score."""
        _, _, adjacent, _ = load_fixtures(FIXTURES_PATH)

        expected, name = calculate_expected_score("carwre", adjacent)

        assert expected > 0.8
        assert name == "Carolina Wren"

    def test_species_in_some_adjacent(self) -> None:
        """Species in some adjacent counties should have proportional expected score."""
        _, _, adjacent, _ = load_fixtures(FIXTURES_PATH)

        expected, name = calculate_expected_score("bkbwar", adjacent)

        # Only in Wake County
        assert expected > 0
        assert name == "Black-and-white Warbler"

    def test_species_not_in_adjacent(self) -> None:
        """Species not in adjacent counties should have zero expected score."""
        _, _, adjacent, _ = load_fixtures(FIXTURES_PATH)

        expected, name = calculate_expected_score("nonexistent", adjacent)

        assert expected == 0.0
        assert name is None


class TestCalculateObservedScore:
    """Tests for calculate_observed_score function."""

    def test_common_species(self) -> None:
        """Common species should have high observed score."""
        _, durham, _, _ = load_fixtures(FIXTURES_PATH)

        observed = calculate_observed_score("norcar", durham)

        assert observed > 0.9  # Northern Cardinal very common

    def test_rare_species(self) -> None:
        """Rare species should have low observed score."""
        _, durham, _, _ = load_fixtures(FIXTURES_PATH)

        observed = calculate_observed_score("kenwar", durham)

        assert observed < 0.05  # Kentucky Warbler is rare

    def test_absent_species(self) -> None:
        """Species not in Durham should have zero observed score."""
        _, durham, _, _ = load_fixtures(FIXTURES_PATH)

        observed = calculate_observed_score("nonexistent", durham)

        assert observed == 0.0


class TestCalculateUnderreportedScores:
    """Tests for calculate_underreported_scores function."""

    def test_returns_sorted_list(self) -> None:
        """Scores should be sorted by underreported_score descending."""
        scores = calculate_underreported_scores(FIXTURES_PATH)

        assert len(scores) > 0
        for i in range(len(scores) - 1):
            assert scores[i].underreported_score >= scores[i + 1].underreported_score

    def test_excludes_excluded_species(self) -> None:
        """Excluded species should not appear in results."""
        scores = calculate_underreported_scores(FIXTURES_PATH)

        species_codes = {s.species_code for s in scores}

        # lotduc and bkcchi are in exclusions.json
        assert "lotduc" not in species_codes
        assert "bkcchi" not in species_codes

    def test_underreported_species_ranked_high(self) -> None:
        """Species present in adjacent but rare in Durham should rank high."""
        scores = calculate_underreported_scores(FIXTURES_PATH)

        # Get top 5 species
        top_codes = [s.species_code for s in scores[:5]]

        # Wood Thrush, Kentucky Warbler, Worm-eating Warbler should be high
        # (common in adjacent, relatively rare in Durham)
        underreported_species = {"woothr", "kenwar", "worwar", "amewoo", "bkbwar"}
        assert any(code in underreported_species for code in top_codes)

    def test_returns_species_score_objects(self) -> None:
        """Each result should be a SpeciesScore with all fields."""
        scores = calculate_underreported_scores(FIXTURES_PATH)

        assert len(scores) > 0
        score = scores[0]

        assert isinstance(score, SpeciesScore)
        assert isinstance(score.species_code, str)
        assert isinstance(score.common_name, str)
        assert isinstance(score.expected_score, float)
        assert isinstance(score.observed_score, float)
        assert isinstance(score.underreported_score, float)

    def test_scores_are_non_negative(self) -> None:
        """All scores should be non-negative."""
        scores = calculate_underreported_scores(FIXTURES_PATH)

        for score in scores:
            assert score.expected_score >= 0
            assert score.observed_score >= 0
            assert score.underreported_score >= 0
