"""CLI entry point for bird_targets."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from bird_targets.export import export_all
from bird_targets.scoring import calculate_underreported_scores


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

    # Calculate scores
    scores = calculate_underreported_scores(fixtures_path)

    # Write output CSV
    output_file = out_path / "targets_ranked.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "species_code",
                "common_name",
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
                    score.expected_score,
                    score.observed_score,
                    score.underreported_score,
                ]
            )

    print(f"Wrote {len(scores)} species to {output_file}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Run the export command to generate GeoJSON layers and dossiers."""
    fixtures_path = Path(args.fixtures)
    out_path = Path(args.out)

    # Validate fixtures path
    if not fixtures_path.exists():
        print(f"Error: Fixtures path does not exist: {fixtures_path}", file=sys.stderr)
        return 1

    # Export all layers and dossiers
    result = export_all(fixtures_path, out_path)

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

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
