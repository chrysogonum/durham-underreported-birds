.PHONY: setup verify test lint fmt smoke integration clean

setup:
	python -m pip install -U pip
	python -m pip install -r requirements.txt

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .

test:
	pytest -q

smoke:
	python -m bird_targets --help

integration:
	python -m bird_targets demo --fixtures tests/fixtures --out outputs/_demo
	test -f outputs/_demo/targets_ranked.csv
	python -m bird_targets export --fixtures tests/fixtures --out outputs/_demo
	test -f outputs/_demo/layers/public_lands.geojson
	test -f outputs/_demo/layers/checklist_density.geojson
	test -f outputs/_demo/layers/survey_targets.geojson
	test -d outputs/_demo/species_dossiers
	test $$(ls outputs/_demo/species_dossiers/*.md 2>/dev/null | wc -l) -ge 3

verify: lint test smoke integration
	@echo "VERIFY_OK"
