"""Tests for the CLI module."""

import csv
import tempfile
from pathlib import Path

import pytest

from bird_targets.__main__ import main

FIXTURES_PATH = Path(__file__).parent / "fixtures"


class TestCLI:
    """Tests for CLI commands."""

    def test_help_returns_zero(self) -> None:
        """--help should return exit code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version_returns_zero(self) -> None:
        """--version should return exit code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_no_args_shows_help(self) -> None:
        """No arguments should show help and return 0."""
        result = main([])
        assert result == 0


class TestDemoCommand:
    """Tests for the demo subcommand."""

    def test_demo_creates_output_file(self) -> None:
        """Demo should create targets_ranked.csv in output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            assert result == 0
            output_file = Path(tmpdir) / "targets_ranked.csv"
            assert output_file.exists()

    def test_demo_output_has_correct_columns(self) -> None:
        """Output CSV should have required columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            output_file = Path(tmpdir) / "targets_ranked.csv"
            with open(output_file) as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

            expected_columns = [
                "species_code",
                "common_name",
                "expected_score",
                "observed_score",
                "underreported_score",
            ]
            assert fieldnames == expected_columns

    def test_demo_output_has_data_rows(self) -> None:
        """Output CSV should contain species data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            output_file = Path(tmpdir) / "targets_ranked.csv"
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) > 0
            # Check that first row has valid data
            first_row = rows[0]
            assert first_row["species_code"]
            assert first_row["common_name"]
            assert float(first_row["expected_score"]) >= 0
            assert float(first_row["observed_score"]) >= 0
            assert float(first_row["underreported_score"]) >= 0

    def test_demo_output_is_sorted_by_underreported_score(self) -> None:
        """Output should be sorted by underreported_score descending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            output_file = Path(tmpdir) / "targets_ranked.csv"
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            scores = [float(row["underreported_score"]) for row in rows]
            assert scores == sorted(scores, reverse=True)

    def test_demo_creates_output_directory(self) -> None:
        """Demo should create output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_out = Path(tmpdir) / "nested" / "output"
            result = main(
                ["demo", "--fixtures", str(FIXTURES_PATH), "--out", str(nested_out)]
            )

            assert result == 0
            assert (nested_out / "targets_ranked.csv").exists()

    def test_demo_invalid_fixtures_returns_error(self) -> None:
        """Demo with invalid fixtures path should return error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main(["demo", "--fixtures", "/nonexistent/path", "--out", tmpdir])

            assert result == 1

    def test_demo_excludes_excluded_species(self) -> None:
        """Output should not contain excluded species."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir])

            output_file = Path(tmpdir) / "targets_ranked.csv"
            with open(output_file) as f:
                reader = csv.DictReader(f)
                species_codes = {row["species_code"] for row in reader}

            # lotduc and bkcchi are excluded
            assert "lotduc" not in species_codes
            assert "bkcchi" not in species_codes

    def test_demo_deterministic_output(self) -> None:
        """Running demo twice should produce identical output."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir1])
                main(["demo", "--fixtures", str(FIXTURES_PATH), "--out", tmpdir2])

                with open(Path(tmpdir1) / "targets_ranked.csv") as f1:
                    content1 = f1.read()
                with open(Path(tmpdir2) / "targets_ranked.csv") as f2:
                    content2 = f2.read()

                assert content1 == content2
