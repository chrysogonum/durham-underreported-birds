"""Scoring module for calculating under-reported species."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SpeciesScore:
    """Score data for a single species."""

    species_code: str
    common_name: str
    expected_score: float
    observed_score: float
    underreported_score: float


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
        checklists = region["checklists_total"]
        if checklists == 0:
            continue

        for sp in region["species"]:
            if sp["species_code"] == species_code:
                rate = sp["observation_count"] / checklists
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
    checklists = durham_data["checklists_total"]
    if checklists == 0:
        return 0.0

    for sp in durham_data["species"]:
        if sp["species_code"] == species_code:
            return sp["observation_count"] / checklists

    return 0.0


def calculate_underreported_scores(
    fixtures_path: Path,
) -> list[SpeciesScore]:
    """Calculate under-reported scores for all species.

    Args:
        fixtures_path: Path to the fixtures directory

    Returns:
        List of SpeciesScore objects sorted by underreported_score descending
    """
    _, durham_data, adjacent_data, exclusions = load_fixtures(fixtures_path)

    # Build set of excluded species codes
    excluded_codes = {sp["species_code"] for sp in exclusions["excluded_species"]}

    # Collect all unique species from adjacent regions
    all_species: dict[str, str] = {}  # species_code -> common_name
    for region in adjacent_data["regions"]:
        for sp in region["species"]:
            if sp["species_code"] not in excluded_codes:
                all_species[sp["species_code"]] = sp["common_name"]

    # Also include Durham species that aren't excluded
    for sp in durham_data["species"]:
        if sp["species_code"] not in excluded_codes:
            all_species[sp["species_code"]] = sp["common_name"]

    # Calculate scores for each species
    scores: list[SpeciesScore] = []
    for species_code, common_name in all_species.items():
        expected, name_from_adjacent = calculate_expected_score(
            species_code, adjacent_data
        )
        observed = calculate_observed_score(species_code, durham_data)

        # Use name from adjacent if we got one (for species not in Durham)
        if name_from_adjacent:
            common_name = name_from_adjacent

        # Under-reported score: how much lower is Durham than expected?
        # Higher score = more under-reported
        if expected > 0:
            underreported = max(0.0, expected - observed)
        else:
            underreported = 0.0

        scores.append(
            SpeciesScore(
                species_code=species_code,
                common_name=common_name,
                expected_score=round(expected, 4),
                observed_score=round(observed, 4),
                underreported_score=round(underreported, 4),
            )
        )

    # Sort by underreported_score descending
    scores.sort(key=lambda s: s.underreported_score, reverse=True)

    return scores
