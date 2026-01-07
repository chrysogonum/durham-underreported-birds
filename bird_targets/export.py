"""Export module for generating GeoJSON layers and species dossiers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from bird_targets.scoring import calculate_underreported_scores

if TYPE_CHECKING:
    from bird_targets.fetcher import EBirdDataCache


def load_public_lands(fixtures_path: Path) -> dict:
    """Load public lands GeoJSON from fixtures."""
    with open(fixtures_path / "public_lands.json") as f:
        return json.load(f)


def load_hotspots(fixtures_path: Path) -> dict:
    """Load hotspots data from fixtures."""
    with open(fixtures_path / "hotspots.json") as f:
        return json.load(f)


def generate_public_lands_geojson(fixtures_path: Path) -> dict:
    """Generate public lands GeoJSON layer.

    Returns a GeoJSON FeatureCollection of public land polygons.
    """
    return load_public_lands(fixtures_path)


def generate_checklist_density_geojson(fixtures_path: Path) -> dict:
    """Generate checklist density GeoJSON layer.

    Returns a GeoJSON FeatureCollection with point features representing
    hotspot locations with checklist density as a property.
    """
    hotspots_data = load_hotspots(fixtures_path)

    features = []
    for hotspot in hotspots_data["hotspots"]:
        feature = {
            "type": "Feature",
            "properties": {
                "loc_id": hotspot["loc_id"],
                "name": hotspot["name"],
                "checklist_count": hotspot["checklist_count"],
                "density_class": _classify_density(hotspot["checklist_count"]),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [hotspot["lon"], hotspot["lat"]],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def _classify_density(checklist_count: int) -> str:
    """Classify checklist count into density categories."""
    if checklist_count >= 800:
        return "high"
    elif checklist_count >= 300:
        return "medium"
    else:
        return "low"


def generate_survey_targets_geojson(fixtures_path: Path) -> dict:
    """Generate survey targets GeoJSON layer.

    Returns a GeoJSON FeatureCollection with polygons representing
    areas recommended for surveys based on under-surveyed public lands.
    """
    public_lands = load_public_lands(fixtures_path)
    hotspots_data = load_hotspots(fixtures_path)

    # Calculate total checklists per public land (simplified)
    features = []
    for land in public_lands["features"]:
        land_name = land["properties"]["name"]

        # Count hotspots/checklists within or near this land (simplified)
        nearby_checklists = 0
        for hotspot in hotspots_data["hotspots"]:
            if land_name.lower().split("--")[0] in hotspot["name"].lower():
                nearby_checklists += hotspot["checklist_count"]

        # Determine priority based on area vs checklist coverage
        area = land["properties"]["area_acres"]
        coverage_ratio = nearby_checklists / area if area > 0 else 0

        if coverage_ratio < 0.1:
            priority = "high"
        elif coverage_ratio < 0.2:
            priority = "medium"
        else:
            priority = "low"

        feature = {
            "type": "Feature",
            "properties": {
                "name": land_name,
                "type": land["properties"]["type"],
                "area_acres": area,
                "checklist_coverage": nearby_checklists,
                "survey_priority": priority,
            },
            "geometry": land["geometry"],
        }
        features.append(feature)

    # Sort by priority (high first)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    features.sort(key=lambda f: priority_order[f["properties"]["survey_priority"]])

    return {"type": "FeatureCollection", "features": features}


def generate_species_dossier(
    species_code: str,
    common_name: str,
    expected_score: float,
    observed_score: float,
    underreported_score: float,
    fixtures_path: Path,
    observer_expected_score: float = 0.0,
    habitat_expected_score: float = 0.0,
    habitat_rationale: str = "",
) -> str:
    """Generate a markdown dossier for a species.

    Returns markdown content for the species dossier.
    """
    # Load regions for context
    with open(fixtures_path / "regions.json") as f:
        regions = json.load(f)

    adjacent_names = [r["name"] for r in regions["adjacent_regions"]]

    # Build habitat section if available
    habitat_section = ""
    if habitat_rationale:
        habitat_section = f"""
## Habitat Rationale

{habitat_rationale}
"""

    content = f"""# {common_name} ({species_code})

## Under-Reported Status

This species is identified as **under-reported** in Durham County relative to
adjacent counties.

### Scores

| Metric | Value |
|--------|-------|
| Observer Expected Score | {observer_expected_score:.4f} |
| Habitat Expected Score | {habitat_expected_score:.4f} |
| Combined Expected Score | {expected_score:.4f} |
| Observed Score | {observed_score:.4f} |
| Under-reported Score | {underreported_score:.4f} |

## Regional Context

**Target Region:** {regions["target_region"]["name"]}

**Adjacent Regions for Comparison:**
{chr(10).join(f"- {name}" for name in adjacent_names)}
{habitat_section}
## Interpretation

- **Observer Expected Score**: Based on reporting rates in adjacent counties
  ({", ".join(adjacent_names)})
- **Habitat Expected Score**: Based on habitat availability on public lands
- **Combined Expected Score**: Weighted combination of observer and habitat signals
- **Observed Score**: Current reporting rate in Durham County
- **Under-reported Score**: Gap between expected and observed
  (higher = more under-reported)

## Survey Recommendations

1. Focus surveys on habitats where this species is typically found
2. Consider time of day and seasonality for optimal detection
3. Prioritize under-surveyed public lands in Durham County

---
*Generated by bird_targets - Durham Under-Reported Birds Project*
"""
    return content


def export_all(fixtures_path: Path, out_path: Path, scores: list | None = None) -> dict:
    """Export all layers and dossiers.

    Args:
        fixtures_path: Path to fixtures directory
        out_path: Output directory
        scores: Optional list of SpeciesScore objects (if not provided, will calculate)

    Returns:
        Summary dict with counts of exported files
    """
    layers_path = out_path / "layers"
    dossiers_path = out_path / "species_dossiers"

    layers_path.mkdir(parents=True, exist_ok=True)
    dossiers_path.mkdir(parents=True, exist_ok=True)

    # Export GeoJSON layers
    layers_exported = 0

    public_lands = generate_public_lands_geojson(fixtures_path)
    with open(layers_path / "public_lands.geojson", "w") as f:
        json.dump(public_lands, f, indent=2)
    layers_exported += 1

    checklist_density = generate_checklist_density_geojson(fixtures_path)
    with open(layers_path / "checklist_density.geojson", "w") as f:
        json.dump(checklist_density, f, indent=2)
    layers_exported += 1

    survey_targets = generate_survey_targets_geojson(fixtures_path)
    with open(layers_path / "survey_targets.geojson", "w") as f:
        json.dump(survey_targets, f, indent=2)
    layers_exported += 1

    # Export species dossiers for top under-reported species
    if scores is None:
        scores = calculate_underreported_scores(fixtures_path)
    dossiers_exported = 0

    # Export top 5 under-reported species (or all if less than 5)
    for score in scores[:5]:
        if score.underreported_score > 0:
            dossier_content = generate_species_dossier(
                species_code=score.species_code,
                common_name=score.common_name,
                expected_score=score.expected_score,
                observed_score=score.observed_score,
                underreported_score=score.underreported_score,
                fixtures_path=fixtures_path,
                observer_expected_score=score.observer_expected_score,
                habitat_expected_score=score.habitat_expected_score,
                habitat_rationale=score.habitat_rationale,
            )
            dossier_file = dossiers_path / f"{score.species_code}.md"
            with open(dossier_file, "w") as f:
                f.write(dossier_content)
            dossiers_exported += 1

    return {
        "layers_exported": layers_exported,
        "dossiers_exported": dossiers_exported,
    }


def generate_species_dossier_from_data(
    species_code: str,
    common_name: str,
    expected_score: float,
    observed_score: float,
    underreported_score: float,
    target_region: str,
    adjacent_regions: list[str],
    observer_expected_score: float = 0.0,
    habitat_expected_score: float = 0.0,
    habitat_rationale: str = "",
) -> str:
    """Generate a markdown dossier for a species without fixtures.

    Returns markdown content for the species dossier.
    """
    # Build habitat section if available
    habitat_section = ""
    if habitat_rationale:
        habitat_section = f"""
## Habitat Rationale

{habitat_rationale}
"""

    content = f"""# {common_name} ({species_code})

## Under-Reported Status

This species is identified as **under-reported** in Durham County relative to
adjacent counties.

### Scores

| Metric | Value |
|--------|-------|
| Observer Expected Score | {observer_expected_score:.4f} |
| Habitat Expected Score | {habitat_expected_score:.4f} |
| Combined Expected Score | {expected_score:.4f} |
| Observed Score | {observed_score:.4f} |
| Under-reported Score | {underreported_score:.4f} |

## Regional Context

**Target Region:** {target_region}

**Adjacent Regions for Comparison:**
{chr(10).join(f"- {name}" for name in adjacent_regions)}
{habitat_section}
## Interpretation

- **Observer Expected Score**: Based on reporting rates in adjacent counties
- **Habitat Expected Score**: Based on habitat availability on public lands
- **Combined Expected Score**: Weighted combination of observer and habitat signals
- **Observed Score**: Current reporting rate in Durham County
- **Under-reported Score**: Gap between expected and observed
  (higher = more under-reported)

## Survey Recommendations

1. Focus surveys on habitats where this species is typically found
2. Consider time of day and seasonality for optimal detection
3. Prioritize under-surveyed public lands in Durham County

---
*Generated by bird_targets - Durham Under-Reported Birds Project*
"""
    return content


def export_all_from_cache(
    cache: "EBirdDataCache",
    out_path: Path,
    scores: list | None = None,
) -> dict:
    """Export layers and dossiers from cached eBird data.

    Args:
        cache: EBirdDataCache instance with fetched data
        out_path: Output directory
        scores: Optional list of SpeciesScore objects (if not provided, will calculate)

    Returns:
        Summary dict with counts of exported files
    """
    from bird_targets.scoring import calculate_scores_from_cache

    layers_path = out_path / "layers"
    dossiers_path = out_path / "species_dossiers"

    layers_path.mkdir(parents=True, exist_ok=True)
    dossiers_path.mkdir(parents=True, exist_ok=True)

    # Get region info from cache
    target_data = cache.get_target_region()
    adjacent_data = cache.get_adjacent_regions()

    target_name = target_data["name"] if target_data else "Durham County"
    adjacent_names = [r["name"] for r in adjacent_data]

    # Generate placeholder GeoJSON layers (minimal for now)
    layers_exported = 0

    # Public lands - empty placeholder
    public_lands = {
        "type": "FeatureCollection",
        "features": [],
    }
    with open(layers_path / "public_lands.geojson", "w") as f:
        json.dump(public_lands, f, indent=2)
    layers_exported += 1

    # Checklist density - empty placeholder
    checklist_density = {
        "type": "FeatureCollection",
        "features": [],
    }
    with open(layers_path / "checklist_density.geojson", "w") as f:
        json.dump(checklist_density, f, indent=2)
    layers_exported += 1

    # Survey targets - empty placeholder
    survey_targets = {
        "type": "FeatureCollection",
        "features": [],
    }
    with open(layers_path / "survey_targets.geojson", "w") as f:
        json.dump(survey_targets, f, indent=2)
    layers_exported += 1

    # Export species dossiers for top under-reported species
    if scores is None:
        scores = calculate_scores_from_cache(cache)
    dossiers_exported = 0

    # Export top 20 under-reported species (or all if less)
    for score in scores[:20]:
        if score.underreported_score > 0:
            dossier_content = generate_species_dossier_from_data(
                species_code=score.species_code,
                common_name=score.common_name,
                expected_score=score.expected_score,
                observed_score=score.observed_score,
                underreported_score=score.underreported_score,
                target_region=target_name,
                adjacent_regions=adjacent_names,
                observer_expected_score=score.observer_expected_score,
                habitat_expected_score=score.habitat_expected_score,
                habitat_rationale=score.habitat_rationale,
            )
            dossier_file = dossiers_path / f"{score.species_code}.md"
            with open(dossier_file, "w") as f:
                f.write(dossier_content)
            dossiers_exported += 1

    return {
        "layers_exported": layers_exported,
        "dossiers_exported": dossiers_exported,
    }
