"""Habitat-based expectation model for species scoring.

This module provides habitat-based species expectation scoring as a complement
to the observer-based (adjacent county) scoring approach.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Default habitat weights by land type
# Maps public land types to habitat tags
DEFAULT_LAND_TYPE_HABITATS: dict[str, list[str]] = {
    "university_forest": ["mature_forest", "mixed_forest", "riparian"],
    "state_park": ["mature_forest", "mixed_forest", "riparian", "open_fields"],
    "state_recreation_area": [
        "lake_wetland",
        "riparian",
        "open_fields",
        "mixed_forest",
    ],
    "regional_park": ["mixed_forest", "riparian", "suburban_edge", "open_fields"],
    "city_park": ["suburban_edge", "open_fields", "mixed_forest"],
    "wildlife_refuge": ["wetland", "mature_forest", "open_fields", "riparian"],
    "nature_preserve": ["mature_forest", "wetland", "riparian"],
}


@dataclass
class HabitatMatch:
    """Describes a habitat match for a species."""

    land_name: str
    land_type: str
    matched_habitats: list[str]
    area_acres: float
    contribution: float  # Weighted contribution to habitat score


@dataclass
class HabitatScore:
    """Habitat-based expectation score for a species."""

    species_code: str
    habitat_expected_score: float
    matched_lands: list[HabitatMatch]
    rule_weight: float


def load_habitat_rules(rules_path: Path) -> dict[str, dict]:
    """Load species habitat rules from JSON file.

    Args:
        rules_path: Path to species_habitat_rules.json

    Returns:
        Dict mapping species_code to habitat rules
    """
    if not rules_path.exists():
        return {}

    with open(rules_path) as f:
        return json.load(f)


def get_land_habitats(
    land_type: str,
    custom_habitats: list[str] | None = None,
) -> list[str]:
    """Get habitat tags for a land type.

    Args:
        land_type: Type of public land (e.g., 'state_park')
        custom_habitats: Optional explicit habitat list from properties

    Returns:
        List of habitat tags
    """
    if custom_habitats:
        return custom_habitats
    return DEFAULT_LAND_TYPE_HABITATS.get(land_type, ["mixed_forest"])


def calculate_habitat_score(
    species_code: str,
    species_rules: dict,
    public_lands: dict,
) -> HabitatScore:
    """Calculate habitat-based expectation score for a species.

    Args:
        species_code: eBird species code
        species_rules: Species' habitat requirements from rules file
        public_lands: Public lands GeoJSON FeatureCollection

    Returns:
        HabitatScore with calculated score and matched lands
    """
    required_habitats = set(species_rules.get("habitats", []))
    rule_weight = species_rules.get("weight", 0.5)

    if not required_habitats:
        return HabitatScore(
            species_code=species_code,
            habitat_expected_score=0.0,
            matched_lands=[],
            rule_weight=rule_weight,
        )

    matched_lands = []
    total_weighted_area = 0.0
    max_possible_area = 0.0

    for feature in public_lands.get("features", []):
        props = feature.get("properties", {})
        land_name = props.get("name", "Unknown")
        land_type = props.get("type", "")
        area_acres = props.get("area_acres", 0)

        # Get habitats for this land (custom or default by type)
        custom_habitats = props.get("habitats")
        land_habitats = set(get_land_habitats(land_type, custom_habitats))

        max_possible_area += area_acres

        # Check for habitat overlap
        matched = required_habitats & land_habitats

        if matched:
            # Weight by proportion of required habitats matched
            match_proportion = len(matched) / len(required_habitats)
            contribution = area_acres * match_proportion

            total_weighted_area += contribution

            matched_lands.append(
                HabitatMatch(
                    land_name=land_name,
                    land_type=land_type,
                    matched_habitats=sorted(matched),
                    area_acres=area_acres,
                    contribution=contribution,
                )
            )

    # Normalize to 0-1 scale based on habitat availability
    if max_possible_area > 0:
        habitat_expected_score = (total_weighted_area / max_possible_area) * rule_weight
    else:
        habitat_expected_score = 0.0

    return HabitatScore(
        species_code=species_code,
        habitat_expected_score=round(habitat_expected_score, 4),
        matched_lands=matched_lands,
        rule_weight=rule_weight,
    )


def calculate_all_habitat_scores(
    rules_path: Path,
    public_lands: dict,
) -> dict[str, HabitatScore]:
    """Calculate habitat scores for all species with rules.

    Args:
        rules_path: Path to species_habitat_rules.json
        public_lands: Public lands GeoJSON FeatureCollection

    Returns:
        Dict mapping species_code to HabitatScore
    """
    rules = load_habitat_rules(rules_path)

    scores = {}
    for species_code, species_rules in rules.items():
        # Skip metadata keys like _comment
        if species_code.startswith("_"):
            continue
        scores[species_code] = calculate_habitat_score(
            species_code, species_rules, public_lands
        )

    return scores


def get_habitat_rationale(habitat_score: HabitatScore) -> str:
    """Generate human-readable habitat rationale for a species.

    Args:
        habitat_score: HabitatScore for the species

    Returns:
        Markdown-formatted rationale string
    """
    if not habitat_score.matched_lands:
        return "No suitable habitat identified on public lands."

    lines = [
        f"**Habitat Score:** {habitat_score.habitat_expected_score:.4f} "
        f"(weight: {habitat_score.rule_weight})",
        "",
        "**Matched Public Lands:**",
    ]

    for match in sorted(
        habitat_score.matched_lands, key=lambda m: m.contribution, reverse=True
    ):
        habitats_str = ", ".join(match.matched_habitats)
        lines.append(
            f"- **{match.land_name}** ({match.land_type}): "
            f"{match.area_acres:,.0f} acres"
        )
        lines.append(f"  - Habitats: {habitats_str}")
        lines.append(f"  - Contribution: {match.contribution:,.1f}")

    return "\n".join(lines)
