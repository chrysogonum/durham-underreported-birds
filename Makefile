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

verify: lint test smoke integration
	@echo "VERIFY_OK"
