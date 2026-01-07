"""Scoring module for calculating under-reported species."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bird_targets.fetcher import EBirdDataCache

# Default weights for combined scoring
DEFAULT_OBSERVER_WEIGHT = 0.7  # alpha
DEFAULT_HABITAT_WEIGHT = 0.3  # beta


@dataclass
class SpeciesScore:
    """Score data for a single species."""

    species_code: str
    common_name: str
    expected_score: float  # Combined score (for backward compatibility)
    observed_score: float
    underreported_score: float
    # New fields for Phase F
    observer_expected_score: float = 0.0
    habitat_expected_score: float = 0.0
    habitat_rationale: str = ""


# Default exclusions for filtering out vagrants, exotics, etc.
DEFAULT_EXCLUSIONS = {
    "excluded_species": [],
    "exclusion_categories": ["pelagic", "vagrant", "exotic", "flyover"],
}

# Regional plausibility thresholds
MIN_ADJACENT_COUNTIES = 3  # Species must be in at least this many adjacent counties
MIN_TOTAL_OBSERVATIONS = 25  # OR have at least this many total observations


def get_plausible_species(
    adjacent_data: dict,
    min_counties: int = MIN_ADJACENT_COUNTIES,
    min_observations: int = MIN_TOTAL_OBSERVATIONS,
) -> set[str]:
    """Get species codes that pass the regional plausibility filter.

    A species is considered plausible for the target region if it satisfies
    at least one of:
    1) Present in >= min_counties adjacent counties, OR
    2) Has >= min_observations total observations across all adjacent counties

    This filters out vagrants and out-of-scope species that appear rarely
    in just one or two adjacent counties.

    Args:
        adjacent_data: Adjacent regions data with species observations
        min_counties: Minimum number of adjacent counties for plausibility
        min_observations: Minimum total observations for plausibility

    Returns:
        Set of species codes that pass the plausibility filter
    """
    # Count presence across counties and total observations per species
    county_counts: dict[str, int] = {}  # species_code -> number of counties
    total_observations: dict[str, int] = {}  # species_code -> total obs count

    for region in adjacent_data.get("regions", []):
        for sp in region.get("species", []):
            code = sp["species_code"]
            obs_count = sp.get("observation_count", 0)

            county_counts[code] = county_counts.get(code, 0) + 1
            total_observations[code] = total_observations.get(code, 0) + obs_count

    # Species passes if in >= min_counties OR has >= min_observations
    plausible = set()
    for code in county_counts:
        if county_counts[code] >= min_counties:
            plausible.add(code)
        elif total_observations.get(code, 0) >= min_observations:
            plausible.add(code)

    return plausible


def calculate_combined_expected(
    observer_expected: float,
    habitat_expected: float,
    observer_weight: float = DEFAULT_OBSERVER_WEIGHT,
    habitat_weight: float = DEFAULT_HABITAT_WEIGHT,
) -> float:
    """Calculate combined expected score from observer and habitat signals.

    Args:
        observer_expected: Score from adjacent county observer data
        habitat_expected: Score from habitat model
        observer_weight: Weight for observer signal (alpha, default 0.7)
        habitat_weight: Weight for habitat signal (beta, default 0.3)

    Returns:
        Combined expected score
    """
    # Normalize weights
    total_weight = observer_weight + habitat_weight
    if total_weight == 0:
        return 0.0

    alpha = observer_weight / total_weight
    beta = habitat_weight / total_weight

    return alpha * observer_expected + beta * habitat_expected


def load_fixtures(fixtures_path: Path) -> tuple[dict, dict, dict, dict]:
    """Load fixture data from the given path.

    Returns:
        Tuple of (regions, durham_species, adjacent_species, exclusions)
    """
    regions_file = fixtures_path / "regions.json"
    durham_file = fixtures_path / "durham_species.json"
    adjacent_file = fixtures_path / "adjacent_species.json"
    exclusions_file = fixtures_path / "exclusions.json"

    with open(regions_file) as f:
        regions = json.load(f)

    with open(durham_file) as f:
        durham_species = json.load(f)

    with open(adjacent_file) as f:
        adjacent_species = json.load(f)

    with open(exclusions_file) as f:
        exclusions = json.load(f)

    return regions, durham_species, adjacent_species, exclusions


def load_from_cache(cache: "EBirdDataCache") -> tuple[dict, dict, dict]:
    """Load data from an eBird cache.

    Args:
        cache: EBirdDataCache instance

    Returns:
        Tuple of (durham_data, adjacent_data, exclusions)
    """
    durham_data, adjacent_data, _ = cache.export_to_fixtures_format()
    return durham_data, adjacent_data, DEFAULT_EXCLUSIONS


def _get_region_denominator(region: dict) -> int:
    """Get the normalization denominator for a region.

    Uses checklists_total if available, otherwise sums all observation counts.
    This allows scoring to work even when the eBird stats endpoint is unavailable.

    Args:
        region: Region data dict with checklists_total and species

    Returns:
        Denominator value for normalizing observation rates
    """
    checklists = region.get("checklists_total", 0)
    if checklists > 0:
        return checklists

    # Fallback: use sum of all observation counts as proxy
    total_obs = sum(sp.get("observation_count", 0) for sp in region.get("species", []))
    return total_obs


def calculate_expected_score(
    species_code: str,
    adjacent_data: dict,
) -> tuple[float, str | None]:
    """Calculate expected presence score based on adjacent counties.

    Returns:
        Tuple of (expected_score, common_name or None)
    """
    total_rate = 0.0
    region_count = 0
    common_name = None

    for region in adjacent_data["regions"]:
        denominator = _get_region_denominator(region)
        if denominator == 0:
            continue

        for sp in region["species"]:
            if sp["species_code"] == species_code:
                rate = sp["observation_count"] / denominator
                total_rate += rate
                region_count += 1
                if common_name is None:
                    common_name = sp["common_name"]
                break

    if region_count == 0:
        return 0.0, common_name

    return total_rate / region_count, common_name


def calculate_observed_score(
    species_code: str,
    durham_data: dict,
) -> float:
    """Calculate observed presence score in Durham."""
    denominator = _get_region_denominator(durham_data)
    if denominator == 0:
        return 0.0

    for sp in durham_data["species"]:
        if sp["species_code"] == species_code:
            return sp["observation_count"] / denominator

    return 0.0


def calculate_underreported_scores(
    fixtures_path: Path,
    apply_plausibility_filter: bool = True,
    habitat_rules_path: Path | None = None,
    observer_weight: float = DEFAULT_OBSERVER_WEIGHT,
    habitat_weight: float = DEFAULT_HABITAT_WEIGHT,
) -> list[SpeciesScore]:
    """Calculate under-reported scores for all species.

    Args:
        fixtures_path: Path to the fixtures directory
        apply_plausibility_filter: Whether to apply the regional plausibility
            filter (default True). Species must be in ≥3 adjacent counties OR
            have ≥25 total observations across adjacent counties.
        habitat_rules_path: Optional path to species_habitat_rules.json
        observer_weight: Weight for observer-based expectation (alpha, default 0.7)
        habitat_weight: Weight for habitat-based expectation (beta, default 0.3)

    Returns:
        List of SpeciesScore objects sorted by underreported_score descending
    """
    from bird_targets.habitat_model import (
        calculate_all_habitat_scores,
        get_habitat_rationale,
    )

    _, durham_data, adjacent_data, exclusions = load_fixtures(fixtures_path)

    # Build set of excluded species codes
    excluded_codes = {sp["species_code"] for sp in exclusions["excluded_species"]}

    # Get plausible species (filter before collecting species list)
    plausible_codes = (
        get_plausible_species(adjacent_data) if apply_plausibility_filter else None
    )

    # Load habitat scores if rules path provided
    habitat_scores: dict = {}
    habitat_rules: dict = {}
    if habitat_rules_path and habitat_rules_path.exists():
        # Load raw rules to get common names
        with open(habitat_rules_path) as f:
            habitat_rules = json.load(f)
        public_lands_path = fixtures_path / "public_lands.json"
        if public_lands_path.exists():
            with open(public_lands_path) as f:
                public_lands = json.load(f)
            habitat_scores = calculate_all_habitat_scores(
                habitat_rules_path, public_lands
            )

    # Collect all unique species from adjacent regions
    all_species: dict[str, str] = {}  # species_code -> common_name
    for region in adjacent_data["regions"]:
        for sp in region["species"]:
            code = sp["species_code"]
            if code in excluded_codes:
                continue
            if plausible_codes is not None and code not in plausible_codes:
                continue
            all_species[code] = sp["common_name"]

    # Also include Durham species that aren't excluded (and pass plausibility)
    for sp in durham_data["species"]:
        code = sp["species_code"]
        if code in excluded_codes:
            continue
        # Durham species are always included (they're observed locally)
        all_species[code] = sp["common_name"]

    # Also include species from habitat rules (they're plausible by definition)
    for code in habitat_scores:
        if code not in excluded_codes and code not in all_species:
            # Get common name from habitat rules, fallback to code
            rule = habitat_rules.get(code, {})
            name = rule.get("common_name", code) if isinstance(rule, dict) else code
            all_species[code] = name

    # Calculate scores for each species
    scores: list[SpeciesScore] = []
    for species_code, common_name in all_species.items():
        observer_expected, name_from_adjacent = calculate_expected_score(
            species_code, adjacent_data
        )
        observed = calculate_observed_score(species_code, durham_data)

        # Use name from adjacent if we got one (for species not in Durham)
        if name_from_adjacent:
            common_name = name_from_adjacent

        # Get habitat expected score
        habitat_expected = 0.0
        habitat_rationale = ""
        if species_code in habitat_scores:
            hs = habitat_scores[species_code]
            habitat_expected = hs.habitat_expected_score
            habitat_rationale = get_habitat_rationale(hs)

        # Calculate combined expected score
        combined_expected = calculate_combined_expected(
            observer_expected,
            habitat_expected,
            observer_weight,
            habitat_weight,
        )

        # Under-reported score: how much lower is Durham than expected?
        # Higher score = more under-reported
        if combined_expected > 0:
            underreported = max(0.0, combined_expected - observed)
        else:
            underreported = 0.0

        scores.append(
            SpeciesScore(
                species_code=species_code,
                common_name=common_name,
                expected_score=round(combined_expected, 4),
                observed_score=round(observed, 4),
                underreported_score=round(underreported, 4),
                observer_expected_score=round(observer_expected, 4),
                habitat_expected_score=round(habitat_expected, 4),
                habitat_rationale=habitat_rationale,
            )
        )

    # Sort by underreported_score descending
    scores.sort(key=lambda s: s.underreported_score, reverse=True)

    return scores


def calculate_scores_from_data(
    durham_data: dict,
    adjacent_data: dict,
    exclusions: dict,
    apply_plausibility_filter: bool = True,
    habitat_scores: dict | None = None,
    habitat_rules: dict | None = None,
    observer_weight: float = DEFAULT_OBSERVER_WEIGHT,
    habitat_weight: float = DEFAULT_HABITAT_WEIGHT,
) -> list[SpeciesScore]:
    """Calculate under-reported scores from raw data.

    This is a more generic version that works with any data source.

    Args:
        durham_data: Target region data with species observations
        adjacent_data: Adjacent regions data
        exclusions: Exclusion rules
        apply_plausibility_filter: Whether to apply the regional plausibility
            filter (default True). Species must be in ≥3 adjacent counties OR
            have ≥25 total observations across adjacent counties.
        habitat_scores: Optional dict of species_code -> HabitatScore
        habitat_rules: Optional dict of species_code -> rule dict (for common names)
        observer_weight: Weight for observer-based expectation (alpha, default 0.7)
        habitat_weight: Weight for habitat-based expectation (beta, default 0.3)

    Returns:
        List of SpeciesScore objects sorted by underreported_score descending
    """
    from bird_targets.habitat_model import get_habitat_rationale

    habitat_scores = habitat_scores or {}
    habitat_rules = habitat_rules or {}

    # Build set of excluded species codes
    excluded_codes = set()
    if "excluded_species" in exclusions:
        excluded_codes = {sp["species_code"] for sp in exclusions["excluded_species"]}

    # Get plausible species (filter before collecting species list)
    plausible_codes = (
        get_plausible_species(adjacent_data) if apply_plausibility_filter else None
    )

    # Collect all unique species from adjacent regions
    all_species: dict[str, str] = {}  # species_code -> common_name
    for region in adjacent_data.get("regions", []):
        for sp in region.get("species", []):
            code = sp["species_code"]
            if code in excluded_codes:
                continue
            if plausible_codes is not None and code not in plausible_codes:
                continue
            all_species[code] = sp["common_name"]

    # Also include Durham species that aren't excluded
    # (Durham species are always included - they're observed locally)
    for sp in durham_data.get("species", []):
        code = sp["species_code"]
        if code not in excluded_codes:
            all_species[code] = sp["common_name"]

    # Also include species from habitat rules (they're plausible by definition)
    for code in habitat_scores:
        if code not in excluded_codes and code not in all_species:
            # Get common name from habitat rules, fallback to code
            rule = habitat_rules.get(code, {})
            name = rule.get("common_name", code) if isinstance(rule, dict) else code
            all_species[code] = name

    # Calculate scores for each species
    scores: list[SpeciesScore] = []
    for species_code, common_name in all_species.items():
        observer_expected, name_from_adjacent = calculate_expected_score(
            species_code, adjacent_data
        )
        observed = calculate_observed_score(species_code, durham_data)

        # Use name from adjacent if we got one (for species not in Durham)
        if name_from_adjacent:
            common_name = name_from_adjacent

        # Get habitat expected score
        habitat_expected = 0.0
        habitat_rationale = ""
        if species_code in habitat_scores:
            hs = habitat_scores[species_code]
            habitat_expected = hs.habitat_expected_score
            habitat_rationale = get_habitat_rationale(hs)

        # Calculate combined expected score
        combined_expected = calculate_combined_expected(
            observer_expected,
            habitat_expected,
            observer_weight,
            habitat_weight,
        )

        # Under-reported score: how much lower is Durham than expected?
        # Higher score = more under-reported
        if combined_expected > 0:
            underreported = max(0.0, combined_expected - observed)
        else:
            underreported = 0.0

        scores.append(
            SpeciesScore(
                species_code=species_code,
                common_name=common_name,
                expected_score=round(combined_expected, 4),
                observed_score=round(observed, 4),
                underreported_score=round(underreported, 4),
                observer_expected_score=round(observer_expected, 4),
                habitat_expected_score=round(habitat_expected, 4),
                habitat_rationale=habitat_rationale,
            )
        )

    # Sort by underreported_score descending
    scores.sort(key=lambda s: s.underreported_score, reverse=True)

    return scores


def calculate_scores_from_cache(
    cache: "EBirdDataCache",
    habitat_scores: dict | None = None,
    habitat_rules: dict | None = None,
    observer_weight: float = DEFAULT_OBSERVER_WEIGHT,
    habitat_weight: float = DEFAULT_HABITAT_WEIGHT,
) -> list[SpeciesScore]:
    """Calculate under-reported scores from an eBird cache.

    Args:
        cache: EBirdDataCache instance with fetched data
        habitat_scores: Optional dict of species_code -> HabitatScore
        habitat_rules: Optional dict of species_code -> rule dict (for common names)
        observer_weight: Weight for observer-based expectation (alpha, default 0.7)
        habitat_weight: Weight for habitat-based expectation (beta, default 0.3)

    Returns:
        List of SpeciesScore objects sorted by underreported_score descending
    """
    durham_data, adjacent_data, exclusions = load_from_cache(cache)
    return calculate_scores_from_data(
        durham_data,
        adjacent_data,
        exclusions,
        habitat_scores=habitat_scores,
        habitat_rules=habitat_rules,
        observer_weight=observer_weight,
        habitat_weight=habitat_weight,
    )
