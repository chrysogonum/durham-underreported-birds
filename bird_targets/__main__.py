"""CLI entry point for bird_targets."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from bird_targets.export import export_all
from bird_targets.scoring import (
    DEFAULT_HABITAT_WEIGHT,
    DEFAULT_OBSERVER_WEIGHT,
    calculate_scores_from_cache,
    calculate_underreported_scores,
)
from bird_targets.server import run_server
from bird_targets.spotfinder import export_spot_guides

# Default path for habitat rules (relative to project root)
DEFAULT_HABITAT_RULES = (
    Path(__file__).parent.parent / "data" / "species_habitat_rules.json"
)


def write_scores_csv(scores: list, output_file: Path) -> None:
    """Write scores to CSV with all columns."""
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "species_code",
                "common_name",
                "observer_expected_score",
                "habitat_expected_score",
                "expected_score",
                "observed_score",
                "underreported_score",
            ]
        )
        for score in scores:
            writer.writerow(
                [
                    score.species_code,
                    score.common_name,
                    score.observer_expected_score,
                    score.habitat_expected_score,
                    score.expected_score,
                    score.observed_score,
                    score.underreported_score,
                ]
            )


def cmd_demo(args: argparse.Namespace) -> int:
    """Run the demo command using fixture data."""
    fixtures_path = Path(args.fixtures)
    out_path = Path(args.out)

    # Validate fixtures path
    if not fixtures_path.exists():
        print(f"Error: Fixtures path does not exist: {fixtures_path}", file=sys.stderr)
        return 1

    # Create output directory
    out_path.mkdir(parents=True, exist_ok=True)

    # Get habitat rules path
    habitat_rules_path = Path(args.habitat_rules) if args.habitat_rules else None

    # Calculate scores
    scores = calculate_underreported_scores(
        fixtures_path,
        habitat_rules_path=habitat_rules_path,
        observer_weight=args.observer_weight,
        habitat_weight=args.habitat_weight,
    )

    # Write output CSV
    output_file = out_path / "targets_ranked.csv"
    write_scores_csv(scores, output_file)

    print(f"Wrote {len(scores)} species to {output_file}")

    # Generate spot guides and species_spots.geojson
    spot_result = export_spot_guides(fixtures_path, out_path, scores)
    guides_dir = out_path / "spot_guides"
    print(
        f"Exported {spot_result['spot_guides_exported']} spot guides to {guides_dir}/"
    )
    n_spots = spot_result["species_spots_features"]
    print(f"Exported species_spots.geojson with {n_spots} spots")

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Run the export command to generate GeoJSON layers and dossiers."""
    fixtures_path = Path(args.fixtures)
    out_path = Path(args.out)

    # Validate fixtures path
    if not fixtures_path.exists():
        print(f"Error: Fixtures path does not exist: {fixtures_path}", file=sys.stderr)
        return 1

    # Calculate scores first (needed for spot guides)
    scores = calculate_underreported_scores(fixtures_path)

    # Export all layers and dossiers
    result = export_all(fixtures_path, out_path, scores=scores)

    layers_dir = out_path / "layers"
    dossiers_dir = out_path / "species_dossiers"
    print(f"Exported {result['layers_exported']} GeoJSON layers to {layers_dir}/")
    print(f"Exported {result['dossiers_exported']} species dossiers to {dossiers_dir}/")

    # Generate spot guides and species_spots.geojson
    spot_result = export_spot_guides(fixtures_path, out_path, scores)
    guides_dir = out_path / "spot_guides"
    n_guides = spot_result["spot_guides_exported"]
    print(f"Exported {n_guides} spot guides to {guides_dir}/")
    n_spots = spot_result["species_spots_features"]
    print(f"Exported species_spots.geojson with {n_spots} spots")

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the map server."""
    out_path = Path(args.out)
    layers_path = out_path / "layers"
    port = args.port

    # Validate layers path
    if not layers_path.exists():
        print(f"Error: Layers path does not exist: {layers_path}", file=sys.stderr)
        print("Run 'bird_targets export' first to generate layers.", file=sys.stderr)
        return 1

    # Start server (pass out_path for access to targets.csv and dossiers)
    server = run_server(out_path, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch eBird data and cache it locally."""
    from bird_targets.ebird_client import require_api_key
    from bird_targets.fetcher import fetch_all_regions

    # Check for API key first (exits if not found)
    require_api_key()

    out_path = Path(args.out)
    years = args.years

    print(f"Fetching eBird data for the last {years} years...")
    print(f"Cache location: {out_path}")
    print()

    try:
        fetch_all_regions(out_path, years=years, verbose=True)
        print()
        print("Fetch complete!")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run analysis on cached eBird data."""
    from bird_targets.export import export_all_from_cache
    from bird_targets.fetcher import EBirdDataCache
    from bird_targets.habitat_model import calculate_all_habitat_scores

    cache_path = Path(args.cache)
    out_path = Path(args.out)

    # Validate cache path
    db_file = cache_path / "ebird_cache.db"
    if not db_file.exists():
        print(f"Error: Cache not found at {cache_path}", file=sys.stderr)
        print("Run 'bird_targets fetch' first.", file=sys.stderr)
        return 1

    # Create output directory
    out_path.mkdir(parents=True, exist_ok=True)

    # Load habitat scores and rules if rules file exists
    habitat_scores = {}
    habitat_rules = {}
    habitat_rules_path = (
        Path(args.habitat_rules) if args.habitat_rules else DEFAULT_HABITAT_RULES
    )
    if habitat_rules_path.exists():
        import json

        # Load raw rules for common names
        with open(habitat_rules_path) as f:
            habitat_rules = json.load(f)

        # Try to load public lands from fixtures or use empty
        public_lands = {"features": []}
        public_lands_path = Path("tests/fixtures/public_lands.json")
        if public_lands_path.exists():
            with open(public_lands_path) as f:
                public_lands = json.load(f)

        habitat_scores = calculate_all_habitat_scores(habitat_rules_path, public_lands)

    # Load cache and calculate scores
    cache = EBirdDataCache(cache_path)
    scores = calculate_scores_from_cache(
        cache,
        habitat_scores=habitat_scores,
        habitat_rules=habitat_rules,
        observer_weight=args.observer_weight,
        habitat_weight=args.habitat_weight,
    )

    # Write output CSV
    output_file = out_path / "targets_ranked.csv"
    write_scores_csv(scores, output_file)

    print(f"Wrote {len(scores)} species to {output_file}")

    # Export layers and dossiers
    result = export_all_from_cache(cache, out_path, scores=scores)
    layers_dir = out_path / "layers"
    dossiers_dir = out_path / "species_dossiers"
    print(f"Exported {result['layers_exported']} GeoJSON layers to {layers_dir}/")
    print(f"Exported {result['dossiers_exported']} species dossiers to {dossiers_dir}/")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="bird_targets",
        description="Under-reported bird species discovery for Durham County, NC",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="bird_targets 0.1.0",
        help="Show version and exit",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Demo subcommand
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run demo using fixture data",
    )
    demo_parser.add_argument(
        "--fixtures",
        required=True,
        help="Path to fixtures directory",
    )
    demo_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for results",
    )
    demo_parser.add_argument(
        "--habitat-rules",
        default=None,
        help="Path to species_habitat_rules.json (optional)",
    )
    demo_parser.add_argument(
        "--observer-weight",
        type=float,
        default=DEFAULT_OBSERVER_WEIGHT,
        help=f"Observer expectation weight (default: {DEFAULT_OBSERVER_WEIGHT})",
    )
    demo_parser.add_argument(
        "--habitat-weight",
        type=float,
        default=DEFAULT_HABITAT_WEIGHT,
        help=f"Habitat expectation weight (default: {DEFAULT_HABITAT_WEIGHT})",
    )
    demo_parser.set_defaults(func=cmd_demo)

    # Export subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Export GeoJSON layers and species dossiers",
    )
    export_parser.add_argument(
        "--fixtures",
        required=True,
        help="Path to fixtures directory",
    )
    export_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for results",
    )
    export_parser.set_defaults(func=cmd_export)

    # Serve subcommand
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start local map server",
    )
    serve_parser.add_argument(
        "--fixtures",
        required=True,
        help="Path to fixtures directory (unused but required for consistency)",
    )
    serve_parser.add_argument(
        "--out",
        required=True,
        help="Output directory containing layers",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    serve_parser.set_defaults(func=cmd_serve)

    # Fetch subcommand
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch eBird data and cache locally",
    )
    fetch_parser.add_argument(
        "--region",
        default="durham",
        help="Target region (default: durham)",
    )
    fetch_parser.add_argument(
        "--adjacent",
        action="store_true",
        default=True,
        help="Include adjacent counties (default: True)",
    )
    fetch_parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="Years of historical data (default: 5)",
    )
    fetch_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for cache",
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # Run subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Run analysis on cached eBird data",
    )
    run_parser.add_argument(
        "--source",
        default="ebird",
        help="Data source (default: ebird)",
    )
    run_parser.add_argument(
        "--cache",
        required=True,
        help="Path to eBird cache directory",
    )
    run_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for results",
    )
    run_parser.add_argument(
        "--habitat-rules",
        default=None,
        help="Path to species_habitat_rules.json",
    )
    run_parser.add_argument(
        "--observer-weight",
        type=float,
        default=DEFAULT_OBSERVER_WEIGHT,
        help=f"Observer expectation weight (default: {DEFAULT_OBSERVER_WEIGHT})",
    )
    run_parser.add_argument(
        "--habitat-weight",
        type=float,
        default=DEFAULT_HABITAT_WEIGHT,
        help=f"Habitat expectation weight (default: {DEFAULT_HABITAT_WEIGHT})",
    )
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
